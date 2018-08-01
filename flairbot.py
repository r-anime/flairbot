import configparser
import praw
import json
import time

print("Reading config")
config = configparser.ConfigParser()
config.read("config.ini")

subreddit = config["Options"]["subreddit"]
interval = int(config["Options"]["interval"])
reminder_age = int(config["Options"]["reminder_age"])
removal_age = int(config["Options"]["removal_age"])
posts_per_run = int(config["Options"]["posts_per_run"])
reminder_message = config["Options"]["reminder_message"]
removal_message = config["Options"]["removal_message"]

# These values are exposed for use in formatted messages, but not directly used
reminder_age_minutes = int(reminder_age / 60)
removal_age_minutes = int(removal_age / 60)

r = praw.Reddit(**config["Auth"])
print(f"Logged in as /u/{r.user.me().name}")
sub = r.subreddit(subreddit)
print(f"Watching /r/{sub.display_name}")

print("Attempting to read last state")
try:
	with open("remindedIds.json", "r") as file:
		remindedIds = json.load(file)
		print("Recovered state from last run")
except:
	print("Failed to recover state from last run, starting fresh")
	remindedIds = []

def main():
	print("Running")

	for post in sub.new(limit=posts_per_run):
		post_age = int(time.time() - post.created_utc)

		if post.link_flair_text or post.link_flair_css_class:
			print(f"Skip    {post.id} (age={post_age}, link_flair_text={repr(post.link_flair_text)}, link_flair_css_class={repr(post.link_flair_css_class)})")

		elif post_age > removal_age:
			print(f"Remove  {post.id} (age={post_age})")

			# We don't need to track the ID anymore because it won't be in /new
			if (post.id in remindedIds):
				remindedIds.pop(remindedIds.index(post.id))

			post.mod.remove()
			post.reply(removal_message.format(
				username=post.author.name,
				reminder_age_minutes=reminder_age_minutes,
				removalAgeMinutes=removalAgeMinutes
			))

		elif post_age > reminder_age and not post.id in remindedIds:
			print(f"Remind  {post.id} (age={post_age})")
			remindedIds.append(post.id)

			post.reply(reminder_message.format(
				username=post.author.name,
				reminder_age_minutes=reminder_age_minutes,
				removalAgeMinutes=removalAgeMinutes
			))

		else:
			print(f"Wait    {post.id} (age={post_age}, reminded={post.id in remindedIds})")

	# Remove post IDs we shouldn't encounter anymore
	# TODO: this isn't perfect, older posts can backflow into /new when removing newer posts
	while len(remindedIds) > posts_per_run:
		remindedIds.pop(0)

	# write IDs to disk so we can resume if a crash occurs
	with open("remindedIds.json", "w") as file:
		json.dump(remindedIds, file)

	print("Finished")


# https://stackoverflow.com/a/25251804
start = time.time()
while True:
	main()
	time.sleep(float(interval) - ((time.time() - start) % interval))
