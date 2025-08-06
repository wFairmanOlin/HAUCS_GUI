#!/bin/bash
pulled_something="Unpacking objects"

cd /home/haucs/Desktop/HAUCS_GUI

status_resp=$(git status -s --untracked-files=no)
echo "$status_resp"

# if no files or just the settings file

if [[ -z "$status_resp" || "$status_resp" == " M code/settings.csv" ]]
then
    pull_resp=$(git pull origin main)
    #if local repo is updated to remote
    if [[ "$pull_resp" == *"$pulled_something"* ]]
    then
        echo "succesfully updated"
        echo "$pull_resp"
    else
        echo "pulled nothing, already up to date"
        echo "$pull_resp"
    fi
else
    echo "local changes present, can't pull"
fi

cd code

echo "running script"
/home/haucs/truck/bin/python3 gui.py $1
