#!/usr/bin/env python3

import configparser
import praw
import json
import time

print("Reading config")
config = configparser.ConfigParser()
config.read("config.ini")

# someone who knows python please tell me there's a better way to do this
subreddit = config["Options"]["subreddit"]
interval = int(config["Options"]["interval"])
reminder_age = int(config["Options"]["reminder_age"])
removal_age = int(config["Options"]["removal_age"])
posts_per_run = int(config["Options"]["posts_per_run"])
reminder_subject= config["Options"]["reminder_subject"]
reminder_message = config["Options"]["reminder_message"]
dry_run = config["Options"].getboolean("dry_run", False)
episode_bot_account = config["Options"]["episode_bot_account"]

# Load flair template IDs
flairs = config["Flairs"]
# Load all removal reasons
removals = config["Removals"]

if dry_run:
	print("  Performing a dry run; no replies or removals will be made")

# These values are exposed for use in formatted messages, but not directly used
reminder_age_minutes = int(reminder_age / 60)
removal_age_minutes = int(removal_age / 60)

r = praw.Reddit(**config["Auth"])
# if not dry_run:
# 	raise Exception
sub = r.subreddit(subreddit)
print(f"Logged in as /u/{r.user.me().name} on /r/{sub.display_name}")

try:
	with open("flairbot_state.json", "r") as file:
		state = json.load(file)
		reminded_ids = state['reminded_ids']
		initial_time = state['initial_time']
	print("Recovered state from last run")
except:
	print("Failed to recover state from last run, starting fresh")
	reminded_ids = []
	initial_time = time.time()


def remind_to_add_flair(submission):
	if dry_run:
		print(f"    confirm remind_flair: {submission.shortlink}")
		return
	try:
		submission.author.message(reminder_subject, reminder_message.format(
			link=submission.shortlink,
			username=submission.author.name,
			removal_age_minutes=removal_age_minutes,
		))
	except Exception as e:
		print(f"    {e!r}")

def remove(post, reason):
	if dry_run:
		print(f"    confirm {reason}: {post.shortlink}")
		return
	if post.approved:
		print(f"    no override of mod aproval: {post.shortlink}")
		return
	try:
		post.mod.remove()
		post.author.message(removals['subject'], removals[reason].format(
			link=post.shortlink,
			username=post.author.name,
			removal_age_minutes=removal_age_minutes,
			episode_bot_account=episode_bot_account,
		))
	except Exception as e:
		print(f"    {e!r}")

def main():
	"""
	Main loop logic:
	- Check all posts in /new
		if post.age < 3 minutes: do nothing
		elif flaired: check flair post validity (resticted content)
		elif not flaired: remind flair
		elif post.age > 15 minutes: remove
	"""
	print("Running")

	for post in sub.new(limit=posts_per_run):
		post_age = int(time.time() - post.created_utc)

		# ignore mod posts
		if post.distinguished:
			print(f"  Mod     {post.id} (author={post.author})")
		# ignore manually approved posts (for sticky, weekly, etc)
		elif post.approved:
			print(f"  Approvd {post.id} (author={post.author}, approved_by={post.approved_by})")
		# ignore posts created before bot started
		# why?
		elif post.created_utc < initial_time:
			print(f"  Too Old {post.id} (age={post_age})")

		# if give three minutes for flairing or correcting flair
		elif post_age < reminder_age:
			print(f"  Too Recent {post.id} (age={post_age})")
			continue

		# if post is flaired, check that the format is correct
		elif post.link_flair_text or post.link_flair_css_class:
			status = check_flair_post_validity(post)
			print(f"  Flaired {post.id} (status={status}, link_flair_text={repr(post.link_flair_text)}, link_flair_css_class={repr(post.link_flair_css_class)})")

		# post is not flaired, remind to flair if not already done
		elif reminder_age <= post_age <= removal_age and post.id not in reminded_ids:
			print(f"  Remind  {post.id} (age={post_age})")
			remind_to_add_flair(post)
			reminded_ids.append(post.id)

		# if the user was reminded (i.e. above code block was hit previously), remove
		# this will leave unflaired posts up under some circumstances, e.g. manual reapproval after removal age
		elif post_age > removal_age and post.id in reminded_ids:
			print(f"  Remove  {post.id} (age={post_age})")
			remove(post, reason='unflaired')
			# We don't need to track the ID anymore because it won't be in /new
			if (post.id in reminded_ids):
				reminded_ids.remove(post.id)

		else:
			print(f"  Wait    {post.id} (age={post_age}, reminded={post.id in reminded_ids})")

	# Remove post IDs we shouldn't encounter anymore
	# TODO: this isn't perfect, older posts can backflow into /new when removing newer posts
	# HACK: multiply by 3 to hopefully prevent any reasonable issues
	while len(reminded_ids) > 3 * posts_per_run:
		reminded_ids.pop(0)

	# write state to disk so we can resume if a crash occurs
	with open("flairbot_state.json", "w") as file:
		json.dump({
			'reminded_ids': reminded_ids,
			'initial_time': initial_time
		}, file)

	print("Finished")

def check_flair_post_validity(post):
	"""
	Check the the type of post works with flairs.
	Logic:
		Discussion - Must be text
		Rewatch - Must be text
		~~Official Media - Can't be single image~~ REMOVED (key visual exemption)
		News - Can't be image
		Fanart - Must be text
		Cosplay - Must be text
		Recommendation - Can't be image
		Episode - Must be by /u/AutoLovepon
	Returns False if post was removed, True otherwise
	"""
	if post.link_flair_template_id == flairs['Discussion']:
		if is_image(post) and not "chart" in post.title.lower():
			remove(post, reason='single_image')
			return 'not_text'
	elif post.link_flair_template_id == flairs['Rewatch']:
		if not is_text(post):
			remove(post, reason='not_text')
			return 'not_text'
	elif post.link_flair_template_id == flairs['News']:
		if is_image(post):
			remove(post, reason='single_image_news')
			return 'single_image_news'
	elif post.link_flair_template_id == flairs['Fanart'] \
			or post.link_flair_template_id == flairs['OC Fanart']:
		if not is_text(post):
			remove(post, reason='not_text_fanart')
			return 'not_text'
	elif post.link_flair_template_id == flairs['Cosplay']:
		if not is_text(post):
			remove(post, reason='not_text')
			return 'not_text'
	elif post.link_flair_template_id == flairs['Recommendation']:
		if is_image(post):
			remove(post, reason='single_image')
			return 'single_image'
	elif post.link_flair_template_id == flairs['Episode']:
		if not post.author.name == episode_bot_account:
			remove(post, reason='not_bot_episode')
			return 'not_bot_episode'
	elif post.link_flair_template_id == flairs['Help']:
		if is_image(post):
			remove(post, reason='not_text_help')
			return 'not_text_help'
	elif post.link_flair_template_id == flairs['Meme']:
		remove(post, reason='meme_post')
		return 'meme_post'
	return "OK"

def is_image(post):
	if post.is_reddit_media_domain:
		# covers i.redd.it
		return True
	if post.is_self:
		return False
	else:
		url = post.url

	if url.endswith('.jpg') \
	   or url.endswith('.png') \
	   or url.endswith('.gif'):
		   return True
	if 'i.imgur.com' in url:
		return True
	if 'pbs.twimg.com' in url:
		return True
	if 'imgur' in url and not ('/a/' in url or 'gallery' in url):
		return True

	return False

def is_text(post):
	return post.is_self and not is_image(post)

if __name__ == "__main__":
	# https://stackoverflow.com/a/25251804
	start = time.time()
	while True:
		main()
		time.sleep(float(interval) - ((time.time() - start) % interval))
