##
# Simple script to poll a duolingo user experience and add a tag to exist.io

# for args/cli interface
import argparse

# for cfg.ini
import configparser

# Duh
import logging

# For proper exit()
import os

# for scraping the page
import requests
from bs4 import BeautifulSoup

# For converting 'when' to a useful object
import datetime
from pytz import timezone

# Exist.io API is JSON, requires that we send JSON data to it...
import json

# Used for deep-merge of config docs
import collections

# Debugging
from prettyprinter import pprint as pp

###
# Begin by configuring logging
LOG_FORMAT = "[%(filename)s : %(lineno)s - %(funcName)20s() ] (%(levelname)10s) %(message)s"

# I can never remember which int is which; so here's a char -> int map so we can leave the configs in char :)
log_levels = {
    # debug
    'd': 10,
    'i': 20,
    # Warning
    'w': 30,
    'e': 40,
    # Critical
    'c': 50
}

# Default log level is INFO
DEFAULT_LOG_LEVEL = 'i'

# Start with INFO level logging
logging.basicConfig(format=LOG_FORMAT, level=log_levels['i'])
log = logging.getLogger(__name__)

DEFAULT_SSM_PATH = '/prod/lambda/duo-to-exist/config'


def _get_params_from_ssm(path='', decrypt=True, iam_profile=''):
    """
    Attempts to get the document that `path` points to from Amazon Simple Systems Manager (ssm).
    If configured, the IAM profile is also used.
    See: https://github.com/aws/amazon-ssm-agent

    :param path:    The full path/name to the parameter that we're to fetch
    :param decrypt: Bool toggle; should the parameter at `path` be decrypted?
    :param iam_profile: String. If set, will be used to configure the iam profile that the ssm client will use

    :return:
    """

    import boto3
    if iam_profile != '':
        log.debug("creating boto session with iam_profile:{}".format(iam_profile))
        # Note: You should never use AWS API keys unless you have to. And if you must use API keys, then you should
        #   NEVER hard code them. This tool will not allow you to use API keys, so there's no risk of hard-coding ;)
        #   Should you want to create a hard-fork, though, this is where you'd want to hard-code in your AWS API keys.
        session = boto3.Session(profile_name=iam_profile)
    else:
        session = boto3.Session()

    # Get a SSM client using the session
    client = session.client('ssm')

    try:
        log.debug("Fetching Parameters from ssm:{} ...".format(path))
        ssm_param_response = client.get_parameter(Name=path, WithDecryption=decrypt)

        log.debug("got ssm data, last updated:{}".format(ssm_param_response['Parameter']['LastModifiedDate']))

        # Return False to indicate that there was an error pulling the params that we expected
        return json.loads(ssm_param_response['Parameter']['Value']) or False

    except Exception as e:
        _e = "Something broke while trying to pull values from SSM. e:{}".format(e)
        log.error(_e)
        raise e


def _parse_cfg(cfg_file=''):
    """
    Validates file and returns an object representing the parsed content of the file
    :param cfg_file: The path to the cfg file we're to validate and parse
    :return: A `dict` representing the parsed config file
    """
    if not os.path.isfile(cfg_file):
        _e = "The config file {} can't be accessed. Does it exist and have correct permissions?".format(cfg_file)
        log.fatal(_e)
        raise Exception(_e)

    log.debug("Parsing config from {}...".format(cfg_file))

    # Stand up config parser and point it @ the file...
    cfg = configparser.ConfigParser()
    cfg.read(cfg_file)

    # Turn the entire parsed document into a dict and return to the caller
    # Thanks to this uber elegant solution: https://stackoverflow.com/a/28990982/1521764
    cfg = {s: dict(cfg.items(s)) for s in cfg.sections()}
    return cfg


def fetch_page(url='', gmt_delta=''):
    """
    Takes a URL and a Timezone. Gets a session cookie, associates a timezone w/ the session
    and then uses the session to request user data

    :param url: The URL of the page to fetch.
    :param gmt_delta:
    :return:
    """

    log.debug("Fetching url:{} gmt_delta:{}".format(url, gmt_delta))

    # We pretend to be a chrome browser...
    initial_headers = {
        'authority': 'duome.eu',
        'pragma': 'no-cache',
        'cache-control': 'no-cache',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/78.0.3904.108 Safari/537.36',

        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,'
                  'application/signed-exchange;v=b3',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'en-US,en;q=0.9',
    }

    # The magic cookie needed before we can get working results
    magic_cookie = "PHPSESSID"

    # The URL parameters we'll pass along when getting a timezone
    tz_params = (
        # We will get a timedelta like -0800 to indicate that we  are -08 hours and 00 min behind GMT
        #   but the duome API will see -0800 as LITERALLY 800 hours behind GMT. Not ideal!
        # So, we str -> int to drop the leading 0, then turn the int back into a string
        #   and then split (at most 1  time) on the 0. Since the only 0's we have are trailing
        #   the split will give us two tokens: the significant bits and the trailing 0's.
        # Just toss the latter token and we have what we need:
        #   -0800 -> -800 -> -8, 00 -> -8
        ##
        ('time', "GMT {}".format(str(int(gmt_delta)).split("0", 1)[0])),
    )

    # Requests w/o a valid PHPSESSID/magic_cookie cookie are denied; we use Session() to manage cookies
    # The cookie manages the time zone...
    s = requests.session()

    # First, ask for *a* session cookie...
    fake = s.get(url, headers=initial_headers)

    # Now that we have a session cookie, set the timezone associated w/ our session...
    tz_resp = s.get('https://duome.eu/tz.php', params=tz_params)
    tz_resp.raise_for_status()

    # Now, theoretically, we have a session cookie that has been associated w/ a timezone
    response = s.get(url, headers=initial_headers)

    # If we don't get a 200, make noise
    response.raise_for_status()

    # Parse HTML and save to BeautifulSoup object¶
    return BeautifulSoup(response.text, "html.parser")


def parse_raw(recent, user_tz):
    """
    Takes the beautiful-soup objects and the user's TZ and returns localized time + exp tuples

    :param recent:
    :param user_tz:
    :return:
    """

    #  Dict to store the date => XP map we'll return to the caller
    sessions = {}

    # process each raw element
    for session in recent:
        # Pull the text out of the HTML element
        # It will look like this:
        #   2019-12-12 16:11:48 · 13XP
        #
        # So just split on the `·` character, trim and done!
        _raw_line = session.text

        # Skip empty lines
        if _raw_line == "":
            continue

        _tokens = _raw_line.split("·")

        # Check that we have the correct number of tokens, otherwise  emit a warning and try parsing the next one...
        if len(_tokens) != 2:
            _e = "unable to parse [{raw}]. Needed exactly 2 _tokens, but got {len}. _tokens:{tok}".format(
                raw=_raw_line,
                len=len(_tokens),
                tok=_tokens
            )
            log.warning(_e)
            continue

        # Otherwise, assume valid split and move on to turning the _when  into a real date
        # Note: it appears that the _when will be the time that the lesson was finished local to the user
        #   and *not* necessarily local to the host that runs this script. This means that the script should be
        #   run in the same time zone as the user, otherwise the definition of "day"
        #   matter, here :)
        ##
        _when = _tokens[0].strip()
        # _when will be in format `2019-12-12 16:11:48` local to  user
        _when = datetime.datetime.strptime(_when, '%Y-%m-%d %H:%M:%S')
        _when = user_tz.localize(_when)

        # In some cases, the secnod token will be in the format of '14XP stories / timed practice' so we must
        #   split *again* on 'XP'
        ##
        _xp = _tokens[1].split('XP')[0].strip()
        _xp = int(_xp)

        log.debug("earned {xp} on {dt}".format(xp=_xp, dt=_when))
        sessions[_when] = _xp

    return sessions


def do_needful(cfg=None):
    """
    The meet of the script.

    :param cfg: `dict` object that should look something like this:
    ```
        {
        'duolingo': {
            'url': 'https://duome.eu/{username}',
            'username': 'kquinsland',
            'timezone': 'US/Pacific',
            'min_xp': '10'
        },
        'exist.io': {
            'tag': 'practice_duolingo',
            'api_token': '<getYourOwn!>',
        }
    }
    ```

    :return:
    """

    # First, make sure that we have a valid CFG.
    if cfg is None:
        cfg = dict()
    if type(cfg) is not dict or 'exist.io' not in cfg:
        _e = "was given an invalid config file. Got:`{}`".format(cfg)
        log.error(_e)
        exit()
    ##
    # Otherwise, cfg should look like this:

    ##
    _duo_cfg = cfg['duolingo']
    _exist_cfg = cfg['exist.io']

    # Localize now() to user time zone, then figure out how far it is from GMT.
    _now = datetime.datetime.now()
    _user_tz = timezone(_duo_cfg['timezone'])
    _now = _user_tz.localize(_now)
    _offset = _now.strftime('%z')

    log.debug("_now:{}".format(_now))
    log.debug("_offset:{}".format(_offset))

    # Build a url from the user name
    _url = _duo_cfg['url'].format(username=_duo_cfg['username'])

    # Pass the URL to fetcher; include time zone so service knows how to localize data for us... (REQUIRED!)
    soup = fetch_page(url=_url, gmt_delta=_offset)

    # The raw data that we care about is located in
    #   <div class="hidden" id="raw">
    # This will be a series of 5 <li> elements, each with the most recent date + the XP level
    raw = soup.find('div', {'class': 'hidden', 'id': 'raw'})

    # From the RAW object, pull the list items
    _recent = raw.find_all('li')

    # Pass the list items off to be processed; get back localized date/time + EXP tuples
    sessions = parse_raw(_recent, _user_tz)

    # The Exist API supports batching, thankfully.
    tags = []

    # Now, go through each session to figure out if the user earned enough XP on that day
    days = {}
    for record in sessions:
        _x = sessions[record]
        _day = record.strftime('%Y-%m-%d')
        days.setdefault(_day, 0)
        days[_day] += _x

    # Now that we have a cumulative XP per day, see if sum is above our threshold
    for day, xp in days.items():
        if xp >= int(_duo_cfg['min_xp']):
            log.info("on {}, you managed to practice enough ({} XPs)!".format(day, xp))
            tags.append(_do_exist_tag_update_payload(day, tag=_exist_cfg['tag']))

    # At this point, we should have an array of objects.
    log.debug("Applying tag to {} days".format(len(tags)))
    do_exist_tag_update(tags, api_token=_exist_cfg['api_token'])


def _do_exist_tag_update_payload(when, tag=''):
    """
    generates an exist.io API payload to apply a tag to a date
    :param when: A datetime object representing when the `tag` is meant to be applied
    :param tag: a `str`; the tag to be applied to `when`
    :return:
    """

    if len(tag) < 1 or type(tag) != str:
        _e = "Asked to apply an invalid tag. got:'{}'".format(tag)
        log.error(_e)
        return False

    return {
        "value": tag,
        "date": when
    }


def do_exist_tag_update(tags=None, api_token=''):
    """
    Takes a list of tags/dates + API token and then applies them to the account in question.

    :param tags: List of tags+dates to apply to a given exist account
    :param api_token: The API token for the exist account in question
    :return:
    """

    if tags is None:
        tags = []
    if len(tags) < 1:
        _e = "Can't apply no tags. Got:{}".format(tags)
        log.error(_e)
        return False

    # TODO: validate API token
    log.info("Batching {} tags for update".format(len(tags)))

    headers = {
        'content-type': 'application/json',
        'authorization': "Bearer {}".format(api_token)
    }

    # We need the Python tags object to be JSON format for the API
    _d = json.dumps(tags)
    resp = requests.post("https://exist.io/api/1/attributes/custom/append/", data=_d, headers=headers)

    # If we didn't get a 200, make noise (will raise HTTPerror)
    resp.raise_for_status()


def parse_args():
    """
    This script does very little, so there's not much to configure. Additionally, what can be configured
        is likely not going to change often so it's best to just leave things in a config file.

    :return:
    """

    # Root argparse
    parser = argparse.ArgumentParser(
        description='Syncs duolingo to Exist.io',
        epilog="That's how you get ants!",
        allow_abbrev=False)

    # Define common args
    # TODO: turn this into more nuanced log level and use logging.getLevelName()
    parser.add_argument("--log-level",
                        default=DEFAULT_LOG_LEVEL,
                        choices=log_levels.keys(),
                        help="set log level (10 thru 50; 10 being debug 50 being critical)"
                        )

    # TODO: integrate w/ git :)
    parser.add_argument('--version', action='version', version='%(prog)s 2.0')

    # Config File Location
    parser.add_argument("--config-file",
                        default='./config.ini',
                        type=str,
                        help="Path to controller config file"
                        )

    parser.add_argument("--use-ssm",
                        action='store_true',
                        help="Include this flag if AWS.SSM.ParameterStore should be consulted...."
                        )

    parser.add_argument("--ssm-path",
                        default=DEFAULT_SSM_PATH,
                        type=str,
                        help="The fully qualified path to the SSM Paramater Store that contains the configuration "
                             "document "
                        )

    parser.add_argument("--iam-profile",
                        default='default',
                        type=str,
                        help="The name of the IAM credential profile to use when communicating with SSM; has no effect"
                             " if --use-ssm is not set"
                        )

    return parser.parse_args()


def lambda_entry(event, context):
    """
    The entry point for AWS Lambda invocation. Does basic parameter collection / validation before invoking the
    do_needful()

    :param event: The object that AWS Lambda will use to pass event data to the function.
    This parameter is usually of the Python dict type. It can also be list, str, int, float, or NoneType type.
    When you invoke your function, you determine the content and structure of the event.
    When an AWS service invokes your function, the event structure varies by service.

    See: https://docs.aws.amazon.com/lambda/latest/dg//python-programming-model-handler-types.html


    :param context: AWS Lambda uses this parameter to provide runtime information to your handler.
    (memory limits, ARNs... etc)
    See: https://docs.aws.amazon.com/lambda/latest/dg//python-context-object.html


    :return:
    """
    log.debug("Alive!")

    # Adjust log level, if set
    if 'log_level' in event:
        log.setLevel(log_levels[event['log_level']])
    else:
        log.setLevel(log_levels[DEFAULT_LOG_LEVEL])

    # Check if the SSM path is set, otherwise use the default
    _c = {
        'ssm_path': DEFAULT_SSM_PATH
    }
    if 'ssm_path' in event:
        _c['ssm_path'] = event['ssm_path']

    log.info("Jumping into function...")
    # Pass the args obj off to the bulk of the code
    do_needful(generate_cfg(_c))

    # Assuming that nothing blew up, exit cleanly :)
    log.info("Exiting...")
    exit(0)


def generate_cfg(args=None):
    """
    Takes Argparse args and, optionally, augments them with values from AWS SSM.ParameterStore.
    The merged object is returned to the caller.

    :param args: Parsed arguments from argparse or a `dict`.
    :return: `dict` w/ a parsed and merged config
    """

    # The CFG object that we'll return to caller
    _cfg = {}

    # If args is an instance of the `argparse.Namespace` class, then we know that argparse was invoked and we will
    #   have command line arguments that we should parse. If args is just a `dict` then it's safe to assume that
    #   argparse was not involved, but the caller has specified some properties that we should consider when building
    #   the config object. Currently, only `ssm_path` is supported via dict
    if isinstance(args, argparse.Namespace):
        log.debug("Args are provided. Parsing...")

        # Args have been given so we're probably running local; parse the config file args points us to and add to _cfg
        _cfg.update(_parse_cfg(args.config_file))

        # Check if the user has instructed us to use SSM, if they have, use the IAM profile given
        if args.use_ssm is True:
            log.debug("... Fetching SSM")
            _do_deep_merge(_cfg, _get_params_from_ssm(path=args.ssm_path, iam_profile=args.iam_profile))

    elif type(args) is dict:
        # Argparse was not used, so assume that caller has set their own SSM path
        log.debug("Args not from argparse, supporting a minimal config set")
        ##
        # When running in lambda, only the path to the SSM store needs to be set; the lambda runtime will already
        #   (read: automatically) have an IAM profile that can be applied :).
        ##
        _do_deep_merge(_cfg, _get_params_from_ssm(path=args['ssm_path']))

    else:
        _e = "Invalid args. Can't generate a config! got:{}" .format(args)
        log.fatal(_e)
        exit(1)

    return _cfg


def _do_deep_merge(dct, merge_dct):
    """
    Recursive dict merge. Inspired by :meth:``dict.update()``, instead of updating only top-level keys,
    dict_merge recurses down into dicts nested to an arbitrary depth, updating keys.
    The ``merge_dct`` is merged into ``dct``.

    Seamlessly stolen from https://gist.github.com/angstwad/bf22d1822c38a92ec0a9
    Credit goes to Copyright (C) 2016 Paul Durivage <pauldurivage+github@gmail.com>

    I only made it python 3.7+ compatible...

    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None


    """
    for k, v in merge_dct.items():
        if (k in dct and isinstance(dct[k], dict)
                and isinstance(merge_dct[k], collections.abc.Mapping)):
            _do_deep_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]


if __name__ == "__main__":
    """
    This script is intended for deployment either in a serverless context (read; aws/lambda) or in a local/cron context
    WHen invoked via regular CLI, this is our entry point.
    
    Parse the passed commandline args, set the log level as instructed, and then enter the main function.  
    """
    # Let the world know we're alive and then begin  parsing args
    log.debug("Alive! Parsing args...")
    args = parse_args()

    # Adjust log level
    log.info("Alive. Adjusting log level to {}..".format(args.log_level))
    log.setLevel(log_levels[args.log_level])

    # Pass the args obj off to the bulk of the code
    do_needful(generate_cfg(args))

    # Assuming that nothing blew up, exit cleanly :)
    log.info("Exiting...")
    exit(0)
