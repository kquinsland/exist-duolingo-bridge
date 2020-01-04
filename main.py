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

# Debugging
from prettyprinter import pprint  as pp


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
    # Crit
    'c': 50
}

# Start with INFO level logging
logging.basicConfig(format=LOG_FORMAT, level=log_levels['i'])
log = logging.getLogger(__name__)

def get_params_from_ssm(param_name):
    import boto3
    client = boto3.client('ssm')
    try:
        ssm_param_response = client.get_parameter(
            Name=param_name,
            WithDecryption=True
        )
        
        raw_params = ssm_param_response['Parameter']['Value']
        return json.loads(raw_params) or {}
    except Exception as e:
        print(e)
        raise e
    

def _parse_cfg(cfg_file=''):
    """
    Validates file and returns an object representing the parsed content of the file
    :param cfg_file:
    :return:
    """
    if not os.path.isfile(cfg_file):
        _e = "The config file {} can't be accessed. Does it exist and have correct permissions?".format(cfg_file)
        log.fatal(_e)
        raise Exception(_e)

    log.debug("Parsing config from {}...".format(cfg_file))

    cfg = configparser.ConfigParser()
    cfg.read(cfg_file)
    return cfg
    

def fetch_page(url='', gmt_delta=''):
    """
    Takes a URL and a Timezone. Gets a session cookie, associates a timezone w/ the session
    and then uses the session to request user data

    :param url:
    :param timezone:
    :return:
    """

    log.debug("Fetching url:{} gmt_delta:{}".format(url,gmt_delta))

    # We pretend to be a chrome browser...
    initial_headers = {
        'authority': 'duome.eu',
        'pragma': 'no-cache',
        'cache-control': 'no-cache',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'en-US,en;q=0.9',
    }


    # The magic cookie needed before we can get working results
    magic_cookie='PHPSESSID'

    # The URL parameters we'll pass along when getting a timezone..
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
        # remove whitespace, drop the XP and turn into INT
        _xp = int(_tokens[1].strip().replace('XP', ''))
        log.debug("earned {xp} on {dt}".format(xp=_xp, dt=_when))
        sessions[_when] = _xp

    return sessions


def do_needful(args):
    """
    The meet of the script.

    :param args:
    :return:
    """
    log.debug("Alive!")

    # Open the config file
    if 'ssm_parameter_name' in args and args['ssm_parameter_name']:
        cfg = get_params_from_ssm(args['ssm_parameter_name'])
    elif 'config_file' in args and args['config_file']:
        cfg = _parse_cfg(args['config_file'])
    else:
        _e = "No Config file or ssm parameter name provided!"
        log.fatal(_e)
        raise Exception(_e)


    # Get the duo section from  cfg parser
    duo_cfg = dict(cfg['duolingo'].items())
    exist_cfg = dict(cfg['exist.io'].items())

    # From the duo config, we need the min_xp and user time zone
    min_xp = int(duo_cfg['min_xp'])
    user_tz = timezone(duo_cfg['timezone'])

    # With the time zone, figure out it's +/- from GMT
    _now = datetime.datetime.now(user_tz)
    _offset = _now.strftime('%z')

    # Build a url from the user name
    url = duo_cfg['url'].format(username=duo_cfg['username'])

    # Pass the URL to fetcher; include time zone so service knows how to localize  data for us... (REQUIRED!)
    soup = fetch_page(url=url, gmt_delta=_offset)

    # The raw data that we care about is located in
    #   <div class="hidden" id="raw">
    # This will be a series of 5 <li> elements, each with the most recent date + the XP level
    raw = soup.find('div', {'class': 'hidden', 'id':'raw'})

    # From the RAW object, pull the list items
    recent = raw.find_all('li')

    # Pass the list items off to be processed; get back localized date/time + EXP tuples
    sessions = parse_raw(recent, user_tz)

    # The Exist API supports batching, thankfully.
    tags = []

    # Now, go through each session to figure out if the user earned enough XP
    days = {}
    for record in sessions:
        _x = sessions[record]
        _day = record.strftime('%Y-%m-%d')
        days.setdefault(_day, 0)
        days[_day] += _x
    
    for day, xp in days.items():
        if xp >= min_xp:
            log.info("on {}, you managed to practice enough ({} XPs)!".format(day, xp))
            tags.append(_do_exist_tag_update_payload(day, tag=exist_cfg['tag']))

    # At this point, we should have an arrayof objexts.
    log.debug("Applying tag to {} days".format(len(tags)))
    do_exist_tag_update(tags, api_token=exist_cfg['api_token'])
    return days


def _do_exist_tag_update_payload(when, tag=''):
    """
    generates an exist.io API payload to apply a tag to a date
    :param tag:
    :param date:
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


def do_exist_tag_update(tags=[], api_token=''):
    """
    Takes a list of tags/dates + API token and then applies them to the account in question.

    :param tag:
    :param date:
    :return:
    """

    if len(tags) < 1:
        _e = "Can't apply no tags. Got:{}".format(tags)
        log.error(_e)
        return False

    # TODO: validate API token
    log.info("Batching {} tags for update".format(len(tags)))

    # TODO: perhaps add support for KMS when deployed to  lambda?
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
        description = 'Syncs duolingo to Exist.io',
        epilog = 'Thats how you get ants!',
        allow_abbrev=False)

    # Define common args
    # TODO: turn this into more nuanced log level and use logging.getLevelName()
    parser.add_argument("--log-level",
                        default='i',  # I for info :)
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


    return parser.parse_args()

def perform(args):
    # Adjust log level
    log.info("Alive. Adjusting log level to {}..".format(args['log_level']))
    log.setLevel(log_levels[args['log_level']])

    # Pass the args obj off to the bulk of the code
    return do_needful(args=args)

def deploy_doulingo_activity_to_exist_io(message, _context):
    message = {
        'config_file': None,
        'log_level': 'i',
        'ssm_parameter_name': None,
        **message
    }
    print(message)
    return {
        "statusCode": 200,
        "body": perform(message)
    }

if __name__ == "__main__":
    # Let the world know we're alive and then begin  parsing args
    log.debug("Alive! Parsing args...")
    args = parse_args()
    
    perform(vars(args))

    # Assuming that nothing bklew up, exit cleanly :)
    log.info("Exiting...")
    os._exit(0)