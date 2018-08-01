# flairbot

A Python script for enforcing post flair requirements on new Reddit posts. Reminds users to flair their posts if they don't within X amount of time, and removes the posts if they still don't after Y amount of time. Built on [PRAW](https://github.com/praw-dev/praw).

## Prerequisites

Note: earlier versions may work fine; these are the lowest *tested* versions.

- Python 3.6+
- Praw 6.x

## Usage

```bash
# install dependencies
pip install -r requirements.txt
# write your config
cp config.sample.ini config.ini && $EDITOR config.ini
# run the bot
python flairbot.py
```

## License

MIT &copy; 2018 The /r/anime mod team
