#!/bin/sh

UPSTREAM=${1:-'@{u}'}
LOCAL=$(sudo git rev-parse @)
REMOTE=$(sudo git rev-parse "$UPSTREAM")
BASE=$(sudo git merge-base @ "$UPSTREAM")

if [ $LOCAL = $REMOTE ]; then
    echo "Program is already up-to date."
elif [ $LOCAL = $BASE ]; then
    echo "Program Update in progress..."
	sudo git pull
	echo "Device restarting now."
	sudo restart now
elif [ $REMOTE = $BASE ]; then
    echo "You've made local changes which is stopping the ability to update your device. Please use 'git stash' if your unsure on what to do."
else
    echo "Diverged"
fi