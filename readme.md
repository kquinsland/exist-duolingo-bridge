# Duolingo to Exist bridge


I use the wonderful [`exist.io`](https://exist.io/) service to generate a variety of personal dashboards.

This is a very small python script that will pull the experience points for a given duolingo user and, 
if the EXP points for a given day is over a user-defined threshold, apply a custom attribute to an exist.io account.

The idea is to have my duolingo sessions automatically reflected in my exist.io account so I don't 
have to do it (read: forget to do it) daily.

Duolingo has [no API](https://forum.duolingo.com/comment/2418289/Public-API-for-DuoLingo), but there is a 
[3rd party service](https://duome.eu/) that seems to provide the info needed to do this.


## Setup

It's a small python script with some pretty standard libraries. 
A [virtual environment](https://docs.python.org/3/library/venv.html) is suggested, but not required.

Developed on a mac, using a very recent version of python 3. Other platforms will probably work. Older versions of 
python3 will probably also work. Your results may differ, of course! Pull requests are welcome, though :)
 
Before setting up the script, you'll need:

- an exist.io API token. See [here](http://developer.exist.io/#authorisation-flow) for instructions on how to get one.
I suggest taking advantage of the [`scope=append`](http://developer.exist.io/#appending-specific-tags) when doing 
the oAuth dance, as that's all that this tool [needs](https://www.owasp.org/index.php/Least_privilege) to function.

- a Duolingo account. Duh. 


You can use `curl` to do most of the oAuth dance, but the wonderful [insomnia](https://insomnia.rest/) client will make
working with the API a bit easier.

Once you have your token, add it to `config.ini` and then install the dependencies: 

```bash
# Check out the repo (or download the zip file and extract...)
$ git clone $repo_url .

# Copy the sample config file
$ cp config.ini.sample config.ini

# Plug in your duo user, exist token/tag and adjust other things as needed
$ $EDITOR config.ini

# Set up a VENV
$ python3 -m venv ./venv

# Load it
$ source venv/bin/activate

# Install the requirements
$ pip3 install -r requirements.txt
```

The tool is quite simple as it only does one thing. The few command line flags that this tool does support
are all pretty reasonable defaults so it's unlikely that you'll need to adjust them. But, if you  do, the `--help` flag
should give you an idea of what you can tweak and how.


## Running

Load up the venv and run the tool. Simple :).
```bash
bash-5.0$ source venv/bin/activate
(venv) bash-5.0$ python3 main.py 
[main.py : 332 -             <module>() ] (      INFO) Alive. Adjusting log level to i..
[main.py : 231 -           do_needful() ] (      INFO) on 2019-12-21 16:49:52-08:00, you managed to practice enough!
[main.py : 231 -           do_needful() ] (      INFO) on 2019-12-23 18:40:36-08:00, you managed to practice enough!
[main.py : 231 -           do_needful() ] (      INFO) on 2019-12-26 17:31:05-08:00, you managed to practice enough!
[main.py : 231 -           do_needful() ] (      INFO) on 2019-12-27 17:47:07-08:00, you managed to practice enough!
[main.py : 231 -           do_needful() ] (      INFO) on 2019-12-28 13:21:59-08:00, you managed to practice enough!
[main.py : 231 -           do_needful() ] (      INFO) on 2019-12-29 11:33:20-08:00, you managed to practice enough!
[main.py : 273 -  do_exist_tag_update() ] (      INFO) Batching 6 tags for update
[main.py : 339 -             <module>() ] (      INFO) Exiting...

```

## Scheduling

You can use any of your favorite tools to schedule the script.

 Due to a limitation w/ the duo.me service, you should run this script *at least* every 7 days that you use 
Duolingo as 7 is the maximum number of days that I can retrieve for a user. 

You do not need to run the script more than once in a 24 hour period.

If you decide to use [AWS Lambda](https://aws.amazon.com/lambda/) to host the function, then be mindful of the 
free-tier limits. Currently, they are [1 Million free lambda invocations/month](https://aws.amazon.com/lambda/pricing/) and interacting with the Parameter Store
is only [$0.05 per 10,000 requests](https://aws.amazon.com/systems-manager/pricing/). 

This may change - without warning from me - at any time, though! 


**Note**: The exist.io API token will expire in 1 year. I strongly suggest making a reminder or calendar entry so you
renew the API token before it stops working!

## Deployment on AWS Lambda

This script can be run locally or on AWS Lambda. As of right now, you'll need to package up the script and it's 
dependencies for deployment. When running on lambda, the command-line arguments are not parsed, so `--config-file` 
can't be used to point to a config file in your deployment package. You will need to create a JSON equivalent
of `config.ini` and store that in the 
[AWS SSM Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html).



1. [Create](https://docs.aws.amazon.com/systems-manager/latest/userguide/param-create-console.html) a **secure** parameter.
The path can be any fully-qualified path you'd like or use the default path as explained below.

The document that you save to the secure parameter store should look something like this: 

```
{
    "duolingo": {
        "url": "https://duome.eu/{username}",
        "username": "some_username",
        "timezone": "Asia/Jerusalem",
        "min_xp": "30"
    },
    "exist.io": {
        "api_token": "asdfghjk34567890xcvbnm",
        "tag": "your_tag"
    }
}
```

You can tag the parameter however you'd like.

2. Zip your pip packages (from your python env folder) together with main.py (all in the same folder level), e.g.:

```
package.zip:
  main.py
  some_package_folder/
  another_package_folder/
```

3. Deploy the Lambda to your AWS account. Use the latest Python version for your runtime selection. 128MB of memory
and ~15 seconds should be plenty. You will need to add an [IAM Policy](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html) 
to the [Execution Role](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html) to permit
the lambda function to access the ssm parameter. 

4. Add a [Scheduled CloudWatch Event](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/Create-CloudWatch-Events-Scheduled-Rule.html)
to execute the function on some regular interval. Suggested intervals in the Scheduling section.



#### Lambda Configuration

Sane default were chosen, but should you need to change  either the log-level or the path to the config document in ssm
you can create a [Test Event](https://aws.amazon.com/blogs/compute/improved-testing-on-the-aws-lambda-console/) to 
specify preferred values. The JSON you provide to a schedule cloud watch event will be identical to the JSON you provide
for a test event.

| Setting     | Default                              | Description                                                                                                            |
|-------------|--------------------------------------|------------------------------------------------------------------------------------------------------------------------|
| `log_level` | `"i"`                                | Adjust the severity threshold for log info. See the `log_levels` dict in `main.py`                                     |
| `ssm_path`  | `"/prod/lambda/duo-to-exist/config"` | The fully qualified path to the SSM Parameter where the config document is stored. See `DEFAULT_SSM_PATH` in `main.py` |
|             |                                      |                                                                                                                        |

 
Your test event should look like:

```
{
  "ssm_path": "your-ssm-param-name",
  "log_level": "d"
}
```



## Support

Is not provided. There's nothing new or innovative about this tool that requires special instruction. Because of that
there are *plenty* of easily googlable tutorials and other  guides/information out there that will almost certainly
be enough to solve your problem.

Having said that, there are two exceptions to the "you're on your own" rule:

0. If there is a **security issue**, please message me **privately** and I will make every reasonable 
effort patch the issue and release updates in a timely manner. I am a fan of 
[Responsible Disclosure](https://en.wikipedia.org/wiki/Responsible_disclosure) and will appreciate you doing the same!

1. If there's a change to the HTML payload that the Duome service provides. If they change how they return HTML, the
logic that parses that HTML will need to change. I'll get to this as I notice and have free time. If you notice and
manage to implement a fix before I do, a PR will be swiftly merged :). 

 
Any GH issue opened that does not match either of the two exceptions will probably be closed unceremoniously.
Issues that are [well written](https://stackoverflow.com/help/how-to-ask) and
[productive](https://www.youtube.com/watch?v=53zkBvL4ZB4) will probably earn some sympathy, depending on how much free
time I have.

For the capable, pull requests are welcome! Please try to adhere to PEP standards!


## License

This code is free to use for all non-commercial purposes. You may not use this code for any commercial purposes.
I'd appreciate credit or notification if you do use this tool, but that's not required.

Because the code is free to use for non commercial purposes, I can not be help responsible for what you do with it.

Likewise, I can't be held responsible for what this code does to you or your computer.

TL;DR:

[![works badge](https://cdn.jsdelivr.net/gh/nikku/works-on-my-machine@v0.2.0/badge.svg)](https://github.com/nikku/works-on-my-machine)


## TODO:

- [ ] Set up github actions to do PEP validation
- [ ] Set up github actions to create lambda ready ZIP file
- [ ] automate token renewal.
- [ ] Make into a deployable Lambda function (provide sample terraform + IAM Policy for SSM)
