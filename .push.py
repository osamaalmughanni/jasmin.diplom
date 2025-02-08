import os
import subprocess
import datetime

# Set the desired email address
EMAIL = "osama@getify.app"

# Define your remote name (usually 'origin') and branch name
REMOTE = "origin"
BRANCH = "main"

# Pull changes from the remote repository
print("Pulling changes from remote repository...")
pull_result = subprocess.run(["git", "pull", REMOTE, BRANCH], capture_output=True, text=True)
print(pull_result.stdout)  # Print pull output
if pull_result.returncode != 0:
    print(f"Error pulling changes: {pull_result.stderr}")
    exit(1)

# Get the current date in the desired format (YYYY-MM-DD)
current_datetime = datetime.datetime.now()
formatted_date = current_datetime.strftime("%Y-%m-%d")

# Check for changes to commit
status_result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
if not status_result.stdout.strip():
    print("No changes to commit.")
    exit(0)

# Set the user email temporarily
print("Setting user email...")
subprocess.run(["git", "config", "user.email", EMAIL])

# Add all changes and commit with the formatted date and time
print("Adding changes...")
add_result = subprocess.run(["git", "add", "."], capture_output=True, text=True)
print(add_result.stdout)  # Print add output
if add_result.returncode != 0:
    print(f"Error adding changes: {add_result.stderr}")
    exit(1)

commit_message = f"Automated commit: {formatted_date} {current_datetime.strftime('%H:%M:%S')}"
print(f"Committing changes with message: '{commit_message}'")
commit_result = subprocess.run(["git", "commit", "-m", commit_message], capture_output=True, text=True)
print(commit_result.stdout)  # Print commit output
if commit_result.returncode != 0:
    print(f"Error committing changes: {commit_result.stderr}")
    exit(1)

# Push changes to the remote repository
print("Pushing changes to remote repository...")
push_result = subprocess.run(["git", "push", REMOTE, BRANCH], capture_output=True, text=True)
print(push_result.stdout)  # Print push output
if push_result.returncode != 0:
    print(f"Error pushing changes: {push_result.stderr}")
    exit(1)

print("Changes pushed successfully.")

# Add a separator line
print("-" * 30)

# Keep the console open
input("Press Enter to exit...")
