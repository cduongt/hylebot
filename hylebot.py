#!/usr/bin/env python3
import socket
import sys
import datetime
import time
from pymongo import MongoClient

############################
## Some helper structures ##
############################

class IrcMessage: # class for storing single IRC message received, basically a singleton
    def __init__(self, whole_message): 
        self.line = whole_message.split(" ", 3)
        for i, line in enumerate(self.line):
            if i == 0:
                self.sender = line.split("!", 1) [0]
            if i == 1:
                self.message_type = line
            if i == 2:
                self.channel = line
            if i == 3:
                self.message = line.strip(":")

def send_message(message): # function which sends a message to connected channel
    irc_socket.send(bytes("PRIVMSG " + channel + " :" + message + "\n", "UTF-8"))
    
################################################################################
##                            Program starts here                             ##
################################################################################

client = MongoClient() # connect to local MongoDB database
db = client.commands

######################
## Channel settings ##
######################

server = "irc.twitch.tv"
channel = "#hylebus"
botnick = "hylebot"
oauthfile = open("oauth.txt", "r") # oauth token is stored in another file for security purposes
modsfile = open("mods.txt", "r") # mod list, file solution until I add it into mongo
oauth = oauthfile.read()
mods = modsfile.read().splitlines()
oauthfile.close()
modsfile.close()

irc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
irc_socket.connect((server, 6667))
irc_socket.send(bytes("PASS " + oauth + "\n", "UTF-8"))
irc_socket.send(bytes("USER " + botnick + " " + botnick + " " + botnick +"\n", "UTF-8"))
irc_socket.send(bytes("NICK Hylebot\n", "UTF-8"))
irc_socket.send(bytes("JOIN " + channel + "\n", "UTF-8"))

connectedFlag = False # flag if bot is fully connected to channel

###########################################################
## Main loop for receiving messages and parsing commands ##
###########################################################

while 1:
    irc_msg = irc_socket.recv(1024).decode("UTF-8")
    irc_msg = irc_msg.strip("\n\r:") # strip extra whitescape

    if irc_msg.find("PING") != -1: # need to keep connection alive
        irc_socket.send(bytes("PONG " + irc_msg.split() [1] + "\n", "UTF-8"))
        continue

    if irc_msg.find("/NAMES") != -1:
        connectedFlag = True
        print("Connected to channel " + channel + ".")
        continue

    if connectedFlag:
        line = IrcMessage(irc_msg) # parse received message, active only after bot is fully connected
        print("[" + time.strftime("%H:%M:%S") + "] " + line.sender + ": " + line.message) # output messages to console
        if line.message.startswith("!"): # parsing channel commands
            if line.message.startswith("!add") and line.sender in mods: # adding new command from chat
                addCommandList = line.message.split(" ", 2)  
                if len(addCommandList) < 3: # test for command syntax "!add !command Command message"
                    send_message("Prikaz neni ve spravnem formatu.")
                    continue

                for i, word in enumerate(addCommandList):
                    if i==1:
                        commandName = word
                    if i==2:
                        commandMessage = word
                        commandUser = line.sender
                        if db.commands.count({"name": commandName}) == 1: # update
                            db.commands.update_one({"name": commandName}, {"$set": {"message": commandMessage, "date": datetime.datetime.utcnow()}})
                            send_message("Prikaz " + commandName + " byl aktualizovan.")
                        else: # insert new
                            command = {"user": commandUser, "name": commandName, "message": commandMessage, "date": datetime.datetime.utcnow()}
                            db.commands.insert_one(command)
                            send_message("Prikaz " + commandName + " byl uspesne zadan do databaze.")
            elif line.message.startswith("!remove") and line.sender in mods:
                removeCommandList = line.message.split(" ", 1)
                if len(removeCommandList) != 2: # "!remove !command"
                    send_message("Prikaz neni ve spravnem formatu.")
                    continue

                if db.commands.delete_one({"name": removeCommandList[1]}).deleted_count > 0:
                    send_message("Prikaz " + removeCommandList[1] + " byl uspesne smazan.")
                else:
                    send_message("Prikaz " + removeCommandList[1] + " neexistuje.")
            else:
                commandList = line.message.split(" ")
                if len(commandList) > 1: # skip if more arguments
                    continue
                commandMessageQuery = db.commands.find({"name": commandList[0]})
                if commandMessageQuery.count() == 0:
                    send_message("Prikaz " + commandList[0] + " neexistuje.")
                else:
                    send_message(commandMessageQuery.distinct("message")[0])
