import configparser
import praw
import json
import time

print("Reading config")
config = configparser.ConfigParser()
config.read("config.ini")

auth = config["Auth"]
options = config["Options"]

interval = int(options["Interval"])
reminderAge = int(options["ReminderAge"])
removalAge = int(options["RemovalAge"])
postsPerRun = int(options["PostsPerRun"])
reminderMessage = options["ReminderMessage"]
removalMessage = options["RemovalMessage"]

# These values are exposed for use in formatted messages, but not directly used
reminderAgeMinutes = int(reminderAge / 60)
removalAgeMinutes = int(removalAge / 60)

print(f"Logging into Reddit as /u/{auth['Username']}")
r = praw.Reddit(
	user_agent=auth["UserAgent"],
	client_id=auth["ClientId"],
	client_secret=auth["ClientSecret"],
	username=auth["Username"],
	password=auth["Password"]
)
print(f"Watching /r/{options['Subreddit']}/new")
sub = r.subreddit(options["Subreddit"])

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

	for post in sub.new(limit=postsPerRun):
		post_age = int(time.time() - post.created_utc)

		if post.link_flair_text or post.link_flair_css_class:
			print(f"Skip    {post.id} (age={post_age}, link_flair_text={repr(post.link_flair_text)}, link_flair_css_class={repr(post.link_flair_css_class)})")

		elif post_age > removalAge:
			print(f"Remove  {post.id} (age={post_age})")

			# We don't need to track the ID anymore because it won't be in /new
			if (post.id in remindedIds):
				remindedIds.pop(remindedIds.index(post.id))

			post.mod.remove()
			post.reply(removalMessage.format(
				username=post.author.name,
				reminderAgeMinutes=reminderAgeMinutes,
				removalAgeMinutes=removalAgeMinutes
			))

		elif post_age > reminderAge and not post.id in remindedIds:
			print(f"Remind  {post.id} (age={post_age})")
			remindedIds.append(post.id)

			post.reply(reminderMessage.format(
				username=post.author.name,
				reminderAgeMinutes=reminderAgeMinutes,
				removalAgeMinutes=removalAgeMinutes
			))

		else:
			print(f"Wait    {post.id} (age={post_age}, reminded={post.id in remindedIds})")

	# Remove post IDs we shouldn't encounter anymore
	# TODO: this isn't perfect, older posts can backflow into /new when removing newer posts
	while len(remindedIds) > postsPerRun:
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
