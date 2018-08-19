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
reminder_message = config["Options"]["reminder_message"]
removal_message = config["Options"]["removal_message"]
dry_run = config["Options"].getboolean("dry_run", False)

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
	# backwards compatibility: remove before next version
	try:
		with open("remindedIds.json", "r") as file:
			reminded_ids = json.load(file)
			initial_time = 0
		print("Loaded reminded IDs from remindedIds.json; assuming no time limit")
	except:
		print("Failed to recover state from last run, starting fresh")
		reminded_ids = []
		initial_time = time.time()


def remind_to_add_flair(submission):
	if dry_run:
		print(f"    confirm: https://redd.it/{submission.id}")
	else:
		try:
			submission.reply(reminder_message.format(
				username=submission.author.name,
				reminder_age_minutes=reminder_age_minutes,
				removal_age_minutes=removal_age_minutes
			))
		except Exception as e:
			print(f"    {e!r}")

def remove_for_missing_flair(submission):
	if dry_run:
		print(f"    confirm: https://redd.it/{submission.id}")
	else:
		try:
			submission.mod.remove()
			submission.reply(removal_message.format(
				username=submission.author.name,
				reminder_age_minutes=reminder_age_minutes,
				removal_age_minutes=removal_age_minutes
			))
		except Exception as e:
			print(f"    {e!r}")

def main():
	print("Running")

	for post in sub.new(limit=posts_per_run):
		post_age = int(time.time() - post.created_utc)

		if post.link_flair_text or post.link_flair_css_class:
			print(f"  Flaired {post.id} (link_flair_text={repr(post.link_flair_text)}, link_flair_css_class={repr(post.link_flair_css_class)})")

		elif post.created_utc < initial_time:
			print(f"  Too Old {post.id} (age={post_age})")

		elif post_age > removal_age:
			print(f"  Remove  {post.id} (age={post_age})")
			remove_for_missing_flair(post)
			# We don't need to track the ID anymore because it won't be in /new
			if (post.id in remindedIds):
				remindedIds.pop(remindedIds.index(post.id))

		elif post_age > reminder_age and not post.id in remindedIds:
			print(f"  Remind  {post.id} (age={post_age})")
			remind_to_add_flair(post)
			remindedIds.append(post.id)

		else:
			print(f"  Wait    {post.id} (age={post_age}, reminded={post.id in remindedIds})")

	# Remove post IDs we shouldn't encounter anymore
	# TODO: this isn't perfect, older posts can backflow into /new when removing newer posts
	# HACK: multiply by 3 to hopefully prevent any reasonable issues
	while len(remindedIds) > 3 * posts_per_run:
		remindedIds.pop(0)

	# write state to disk so we can resume if a crash occurs
	with open("flairbot_state.json", "w") as file:
		json.dump({
			'reminded_ids': reminded_ids,
			'initial_time': initial:time
		}, file)

	print("Finished")

if __name__ == "__main__":
	# https://stackoverflow.com/a/25251804
	start = time.time()
	while True:
		main()
		time.sleep(float(interval) - ((time.time() - start) % interval))
