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

The tool is quite simple as it only does one thing.  The few command line flags that this tool does support
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

You can use any of your favorite tools to schedule the script. There's no need to run more than once a day, but you can 
also run it every 5 days that you practice Duolingo. This is because the duo.me service returns the last 5 days that
a user has EXP for. In any event, the script - when combined with a virtual-env - is standalone and should be very 
easy to  get working with your favorite schedule tool.


**Note**: The exist.io API token will expire in 1 year. I strongly suggest making a reminder or calendar entry so you
renew the API token before it stops working!


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

For the capable, pull requests are welcome!


## License

This code is free to use for all non-commercial purposes. You may not use this code for any commercial purposes.
I'd appreciate credit or notification if you do use this tool, but that's not required.

Because the code is free to use for non commercial purposes, I can not be help responsible for what you do with it.

Likewise, I can't be held responsible for what this code does to you or your computer.

TL;DR:

[![works badge](https://cdn.jsdelivr.net/gh/nikku/works-on-my-machine@v0.2.0/badge.svg)](https://github.com/nikku/works-on-my-machine)
 
  
 


## TODO:

- [ ] automate token renewal
- [ ] Finish Dockerization
- [ ] Make into a deployable Lambda function
