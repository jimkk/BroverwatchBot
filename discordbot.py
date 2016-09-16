import discord
import asyncio
import time
from gtts import gTTS
from tempfile import NamedTemporaryFile
import os
import pickle
import cowsay
import urllib.request
import requests
from bs4 import BeautifulSoup
from shutil import copyfile
import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plot

client = discord.Client()

player_lock = asyncio.Lock()
tts_lock = asyncio.Lock()

enabled = True
message_channel = None
admin_channel = None
tts_flag = False
use_avconv = True

nicknames = {}
blacklist = []

helpmsg = """ COMMAND LIST:
>!bbhelp / !bb    -    Display help message
>!bbon / !gogogadgetbot    -    Enable the bot
>!bbmute / !shutup    -    Disable TTS
>!bbunmute / !speakup    -    Enable TTS
>!bbjoin / !joinvoice    -    Invite bot to current vchat
>!bbleave / !leavevoice    -    Remove bot from vchat
>!bboff / !goaway    -    Disable the bot
>!bbsay <line>    -    Say a line in current channel
>!bbnickname <nickname>    -    Set TTS nickname
>!bbcleanup <num>   -    Removes all useless messages in last <num> (default: 25)
>!bbcowsay <words>   -    Say it with a cow
>!bbwiki <searchterm>    -    Links the Overwatch Wikipage for <searchterm>
>!bbsr <int>    -    Stores your current rating
>!bbplotsr  <date/game>    -    Show a graph of your rating (by date or by game)
>!bbundosr    -    Remove your last entered Skill Rating"""

@client.event
@asyncio.coroutine
def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')
    load_nicknames()
    load_blacklist()
    load_admin_channel()

@client.event
@asyncio.coroutine
def on_message(message):
    global message_channel
    global admin_channel
    global tts_flag
    global enabled

    #print(message.author.name)
    #print(message.content)
    log("["+message.server.name+"/"+message.channel.name+"] " + message.author.name + ": " + message.content)
    if(message.author.id in blacklist):
        #nothing should happen if a user is in the blacklist
        if (message.content.startswith('!bb')):
            #yield from client.send_message(message.channel, message.author.mention + "https://giphy.com/gifs/naru-13r5cLwRjhteQE")
            print(message.author.name + " tried to say \""+message.content+"\" but is blacklisted")
        return
    elif (message.content.startswith('!gogogadgetbot') or message.content.startswith('!bbon')):
        yield from client.send_message(message.channel, 'It\'s a me, Broverwatch Bot!')
        log("Bot enabled by " + message.author.name)
        enabled = True
    elif (message.content.startswith('!bbhelp') or message.content.startswith('!bb ') or message.content == '!bb'):
            yield from client.send_message(message.channel, helpmsg)
            log("Bot help message requested by " + message.author.name)
    elif enabled:
        if message.content.startswith('!bbsay'):
            log("Audio line request by " + message.author.name)
            yield from say(message)        
        elif (message.content.startswith('!shutup') or message.content.startswith('!bbmute')):
            tts_flag = False
            yield from client.send_message(message.channel, 'I will go quietly into that good night')
            log("Bot muted by " + message.author.name)
        elif (message.content.startswith('!speakup') or message.content.startswith('!bbunmute')):
            tts_flag = True
            yield from client.send_message(message.channel, 'I will not go quietly into that good night')
            log("Bot unmuted by " + message.author.name)
        elif message.content.startswith('!bbnickname'):
            if len(message.content.split(' ')) < 2:
                yield from client.send_message(message.channel, 'Bad formatting: !bbnickname <nickname>')
            else:
                requested_nickname = message.content[12:]
                set_nickname(message.author, requested_nickname)
                if requested_nickname != 'reset':
                    yield from client.send_message(message.channel, message.author.mention + ' your nickname is now ' + requested_nickname)
        elif (message.content.startswith('!joinvoice') or message.content.startswith('!bbjoin')):
            if message.author.voice_channel == None:
                yield from client.send_message(message.channel,
                message.author.mention + ' You are not in a voice channel')
            else:
                log("Bot joining voice with " + message.author.name)
                yield from client.join_voice_channel(message.author.voice_channel)
        elif (message.content.startswith('!leavevoice') or message.content.startswith('!bbleave')):
            print("Leaving voice for " + message.server.name + " server")
            log("Bot leaving voice for " + message.author.name)
            if client.is_voice_connected(message.server):
                yield from client.voice_client_in(message.server).disconnect()
            else:
                print("ERROR: Not connected to voice channel in this server")
        elif (message.content.startswith('!goaway') or message.content.startswith('!bboff')):
            log("Bot disabled by " + message.author.name)
            yield from client.send_message(message.channel, 'Ok, going away')
            enabled = False
        elif (message.content.startswith('!bbmyson')):
            log("Bot audiolist requested by " + message.author.name)
            yield from client.send_message(message.channel, 'Overwatch: \n' + listlines("res/audioclips/ow"))
            yield from client.send_message(message.channel, 'Wow: \n' + listlines("res/audioclips/wow"))
            yield from client.send_message(message.channel, 'Hearthstone: \n' + listlines("res/audioclips/hs"))
        elif (message.content.startswith('!bbcleanup')):
            log("Cleanup requested by " + message.author.name)
            yield from cleanup(message)
        elif (message.content.startswith('!bbcowsay')):
            log("Cowsay by " + message.author.name)
            yield from bbcowsay(message)
        elif (message.content.startswith('!bbwiki')):
            log("Wiki search by " + message.author.name)
            yield from wikisearch(message)
        elif (message.content.startswith('!bbsr')):
            log("Rating stored by " + message.author.name)
            success = store_rating(message)
            if(not success):
                yield from client.send_message(message.channel, 'Rating store failed.')
            else:
                yield from client.send_message(message.channel, get_rating_change(message.author.id))
        elif (message.content.startswith('!bbplotsr')):
            ret = False
            if(len(message.content.split()) == 1 or message.content.split()[1].startswith('g')):
                ret = plot_rating_game(message.author.id, message.author.name)
            elif message.content.split()[1].startswith('d'):
                ret = plot_rating_date(message.author.id, message.author.name)
            if(ret):
                yield from client.send_file(message.channel, "data/plot.png")
                os.remove("data/plot.png")
        elif (message.content.startswith('!bbundosr')):
            ret = undo_rating_entry(message.author.id)
            if(ret):
                yield from client.send_message(message.channel, 'Last rating deleted.')
            else:
                yield from client.send_message(message.channel, 'Rating not deleted. Your file may be empty or nonexistent.')
        elif message.content.startswith('!bbsetadminchannel') and admin_channel == None:
            log("Admin channel set by " + message.author.name)
            set_admin_channel(message.channel)
            yield from client.send_message(message.channel, 'This channel is now the admin channel') 
        elif message.channel.id == admin_channel and message.content.startswith('!bbblacklist'):
            log("Blacklist requested by " + message.author.name)
            username = message.content.split(" ")[1]
            added = add_to_blacklist(username)
            if added:
                yield from client.send_message(message.channel, "Added " +  username + " to blacklist")
            else:
                yield from client.send_message(message.channel, "Removed " +  username + " from blacklist")
        elif message.channel.id == admin_channel and message.content.startswith('!bblogdump'):
            log("Log dump requested by " + message.author.name)
            yield from dump_log()

@client.event
@asyncio.coroutine
def on_voice_state_update(before, after):
    global message_channel
    global tts_flag
    global enabled
    log("Voice state change for user " + before.name)
    if enabled and not client.user == before: #the updated user is not the bot
        if before.voice_channel == after.voice_channel:
            return
        if client.is_voice_connected(after.server):
            voice_client = client.voice_client_in(after.server)
            if voice_client.channel == after.voice_channel:
                if(after.id in nicknames):
                    yield from tts_voice_clip(voice_client, nicknames[after.id] + ' has joined')
                else:
                    yield from tts_voice_clip(voice_client, after.name + ' has joined')
        if client.is_voice_connected(before.server):
            voice_client = client.voice_client_in(before.server)
            if voice_client.channel == before.voice_channel:
                if before.id in nicknames:
                    yield from tts_voice_clip(voice_client, nicknames[before.id] + ' has left')
                else:
                    yield from tts_voice_clip(voice_client, after.name + ' has left')
    if client.is_voice_connected(before.server) and before.voice_channel == client.voice_client_in(before.server) and len(before.voice_channel.voice_members) == 1:
        yield from client.voice_client_in(before.server).disconnect()
                
def say(message):
    if(len(message.content.split(' ')) == 1):
        yield from client.send_message(message.channel, 'Please give a voice line: \"!bbsay <voiceline>\"')
        return
    
    line = message.content.split(' ', 1)[1]
    line.replace(' ', '/', 1)
    line = line.split(' ')[0]
    path = ''
    if(len(line.split('/')) > 1):
        path = line.rsplit('/',1)[0] + '/' #reverse split at last slash
        line = line.rsplit('/',1)[1]       #reverse split at last slash

    filename = getline(line, path)
    #debugging message
    #yield from client.send_message(message.channel, filename)
    if(filename == None):
        yield from client.send_message(message.channel, 'Voice clip not found. RIP.')
    elif message.author.voice_channel != None and client.voice_client_in(message.server) == None: #author is in vchat bot isnt
        voice_client = yield from client.join_voice_channel(message.author.voice_channel)

        yield from voice_clip(voice_client, filename)
        yield from voice_client.disconnect()
    elif message.author.voice_channel != None and client.voice_client_in(message.server) == message.author.voice_channel: #both in same voice chat
        voice_client = client.voice_client_in(message.server)
        yield from voice_clip(voice_client, filename)
    elif message.author.voice_channel != None and client.voice_client_in(message.server) != message.author.voice_channel: #both in different voice chat
        voice_client = client.voice_client_in(message.server)
        prev_channel = voice_client.channel
        yield from voice_client.move_to(message.author.voice_channel);

        yield from voice_clip(voice_client, filename)
        yield from voice_client.move_to(prev_channel);

def getline(name, path):
    root = 'res/audioclips/' + path
    filename = searchdir(name, root, True)

    if filename == None:
        filename = searchdir(name, root, False)
    
    return filename

def searchdir(name, root, strict):
    #recursive: search dir for file, then search all subdir
    #if strict == False, return anything that has a filename starting with name
    filename = root + name + '.mp3'
    if os.path.isfile(filename) == True:
        return filename
    for x in os.listdir(root):
        #debug searching message
        #print(x + " starts with " + name + " ?")
        if x.startswith(name) and strict == False:
            return root + x
    for x in os.listdir(root):
        if os.path.isdir(root + x):
            subsearch = searchdir(name, (root + x + '/'), strict)
            if subsearch != None:
                return subsearch
    return None

def listlines(dir):
    return ' \\ '.join(x.replace('.mp3', '') for x in os.listdir(dir))

def voice_clip(voice_client, filename):
    global use_avconv
    with(yield from player_lock):
        player = voice_client.create_ffmpeg_player(filename, use_avconv=use_avconv)
        player.start()
        while not player.is_done():
            yield from asyncio.sleep(1)

def tts_voice_clip(voice_client, text):
    with(yield from tts_lock):
        tts = gTTS(text=text, lang='en')
        tts.save('data/tts.mp3')
        yield from voice_clip(voice_client, 'data/tts.mp3')
        os.remove('data/tts.mp3')

def set_nickname(user, nickname):
    global nicknames
    if nickname == 'reset':
        del nicknames[user.id]
    else:
        nicknames[user.id] = nickname
    pkl_file = open('data/nicknames.pkl', 'wb')
    pickle.dump(nicknames, pkl_file)
    pkl_file.close()

def load_nicknames():
    global nicknames
    if(os.path.isfile('data/nicknames.pkl') == True):
        pkl_file = open('data/nicknames.pkl', 'rb')
        nicknames = pickle.load(pkl_file)
        pkl_file.close()

def add_to_blacklist(username):
    global blacklist
    added = False
    user_id = get_id(username)
    if user_id in blacklist:
        blacklist.remove(user_id)
    else:
        blacklist.append(user_id)
        added = True
    pkl_file = open('data/blacklist.pkl', 'wb')
    pickle.dump(blacklist, pkl_file)
    pkl_file.close()

    return added

def load_blacklist():
    global blacklist
    if(os.path.isfile('data/blacklist.pkl') == True):
        pkl_file = open('data/blacklist.pkl', 'rb')
        blacklist = pickle.load(pkl_file)
        pkl_file.close()

def get_id(identifier):
    #given id or username returns a matching id
    members = client.get_all_members()
    for member in members:
        if member.name == identifier:
            return member.id
        if member.id == identifier:
            return identifier

def set_admin_channel(channel):
    global admin_channel
    admin_channel = channel.id
    pkl_file = open('data/admin.pkl', 'wb')
    pickle.dump(admin_channel, pkl_file)
    pkl_file.close()

def load_admin_channel():
    global admin_channel
    if(os.path.isfile('data/admin.pkl') == True):
        pkl_file = open('data/admin.pkl', 'rb')
        admin_channel = pickle.load(pkl_file)
        pkl_file.close()
            
def cleanup(message):
    num = 25
    if(len(message.content.split(' ')) > 1):
        num = int(message.content.split(' ')[1])
        if num > 100:
            num = 100
    print("Purging last " + str(num) + " messages from " + message.channel.name + " channel")
    yield from client.purge_from(message.channel, limit=num,check=isuseless)

def isuseless(message):
    if message.content.startswith('!bb'): #remove bbsay commands
        return True
    elif message.content.startswith('Voice clip not found. RIP.'): #remove failed bbsay responses
        return True
    elif message.content.startswith('Please give a voice line:'): #remove failed bbsay responses
        return True
    elif message.content.startswith(' COMMAND LIST:'): #remove bb / bbhelp responses
        return True
    elif message.content.startswith('Overwatch:') and message.author == client.user: #remove bbmyson output
        return True
    elif message.content.startswith('Wow:') and message.author == client.user: #remove bbmyson output
        return True
    elif message.content.startswith('Hearthstone:') and message.author == client.user: #remove bbmyson output
        return True
    return False

def bbcowsay(message):
    if(len(message.content.split(' ',1)) == 1):
        yield from client.send_message(message.channel, 'Give him something to say: \"!bbcowsay <words>\"')
        return
    text = message.content.split(' ',1)[1]
    #three backticks (``` on the tilde key) creates a code block thank you discord devs
    yield from client.send_message(message.channel, "```" + cowsay.cowsay(text)+"```")
    #print("\n" + cowsay.cowsay(text))

def wikisearch(message):
    if(len(message.content.split(' ')) == 1):
        yield from client.send_message(message.channel, 'Please give a search term: \"!bbwiki <searchterm>\"')
        return
    searchterm = message.content.split(' ', 1)[1];
    searchterm.replace(' ', '+')
    var = requests.get((r'http://www.google.com/search?btnI=I%27m+Feeling+Lucky&ie=UTF-8&oe=UTF-8&q=' + searchterm + r'+site:overwatch.gamepedia.com'))
    
    url = var.url
    if(url.startswith('http://overwatch.gamepedia.com')):
        yield from client.send_message(message.channel, url)
        return

    soup = BeautifulSoup(var.text, "html.parser")
    #print(url)
    if(len(soup.findAll('div', attrs={'class':'g'})) == 0):
        #print(str(var.is_redirect))
        yield from client.send_message(message.channel, 'No results found. RIP.')
        return
    #print(str(soup.findAll('div', attrs={'class':'g'})[0]).encode('utf-8').strip())
    #print(str(soup.findAll('div', attrs={'class':'g'})[0].find('a')).encode('utf-8').strip())
    #print(str(soup.findAll('div', attrs={'class':'g'})[0].find('a')['href']).encode('utf-8').strip())
    url = str(soup.findAll('div', attrs={'class':'g'})[0].find('a')['href'])
    url = url.replace(r'/url?q=', '')
    url = url.rsplit('&')[0]
    #print(url)
    if(not url.startswith('http://overwatch.gamepedia.com')):
        print(url)
        yield from client.send_message(message.channel, 'No results found. RIP.')
        return
    yield from client.send_message(message.channel, url)

def log(message):
    if(not os.path.isfile("data/log")):
        logfile = open("data/log","w")
        logfile.close
    with open("data/log", "a") as logfile:
        logfile.write(datetime.datetime.now().isoformat() + " " + message+"\n")
        logfile.close()

def store_rating(message):
    filename = "data/ratings/"+message.author.id
    text = message.content.replace("!bbsr ","")
        
    try:
        rating = int(text)
    except ValueError:
        return False
    if(rating < 0 or rating > 5000):
        return False

    if(not os.path.isdir("data/ratings")):
        os.makedirs("data/ratings")
    if(not os.path.isfile(filename)):
        ratingfile = open(filename, "w")
        ratingfile.close()
    with open(filename, "a") as ratingfile:
        ratingfile.write(datetime.datetime.now().isoformat() + " " + str(rating)+"\n")
        ratingfile.close()

    return True

def get_rating_change(userid):
    filename = "data/ratings/"+userid
    with open(filename, "r") as ratingfile:
        array = []
        for line in ratingfile:
            array.append(line.split()[1])

    if(len(array) == 1):
        return "This was your first submitted rating."
    currentrating = int(array[len(array)-1])
    oldrating = int(array[len(array)-2])
    message = "Your old rating was "+ str(oldrating) + ". This was a change of " + str(currentrating-oldrating) + "."
    return message

def plot_rating_date(userid, name):
    filename = "data/ratings/" + userid
    if(not os.path.isfile(filename)):
        return False
    datelist = []
    ratings = []
    with open(filename, "r") as ratingfile:
        for line in ratingfile:
            datelist.append(line.split()[0])
            ratings.append(line.split()[1])
    if(len(datelist) < 2):
        return False
    dates = [datetime.datetime.strptime(i, '%Y-%m-%dT%H:%M:%S.%f') for i in datelist]
    fig = plot.figure()
    plot.xlabel('Date')
    plot.ylabel('Skill Rating')
    fig.suptitle(name + '\'s Skill Rating')
    ax = fig.add_subplot(111)
    if(len(ratings)<20):
        for xy in zip(dates, ratings):
            ax.annotate('%s' % xy[1], xy=xy, textcoords='data')
    else:
        interval = len(ratings)/20
        index = 0.0
        points = list(zip(dates, ratings))
        while(round(index) < len(ratings)):
            ax.annotate('%s' % points[int(round(index))][1], xy=points[int(round(index))], textcoords='data')
            index = index + interval
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y/%m/%d %H:%M"))
    ax.plot(dates, ratings, marker='.')
    fig.autofmt_xdate()
    plot.savefig("data/plot.png")
    return True

def plot_rating_game(userid, name):
    filename = "data/ratings/" + userid
    if(not os.path.isfile(filename)):
        return False
    indexes = []
    ratings = []
    with open(filename, "r") as ratingfile:
        for line in ratingfile:
            ratings.append(line.split()[1])
    if(len(ratings) < 2):
        return False
    indexes = range(len(ratings))
    fig = plot.figure()
    fig.suptitle(name + '\'s Skill Rating')
    plot.ylabel('Skill Rating')
    plot.xlabel('Games')
    ax = fig.add_subplot(111)
    if(len(ratings)<20):
        for xy in zip(indexes, ratings):
            ax.annotate('%s' % xy[1], xy=xy, textcoords='data')
    else:
        interval = len(ratings)/20
        index = 0.0
        points = list(zip(indexes, ratings))
        while(round(index) < len(ratings)):
            ax.annotate('%s' % points[int(round(index))][1], xy=points[int(round(index))], textcoords='data')
            index = index + interval
    #ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y/%m/%d %H:%M"))
    ax.plot(indexes, ratings, marker='.')
    #fig.autofmt_xdate()
    plot.savefig("data/plot.png")
    return True

def undo_rating_entry(userid):
    filename = "data/ratings/" + userid
    if(not os.path.isfile(filename)):
        return False
    file = open(filename, "r");
    lines = file.readlines()
    file.close()
    if(len(lines)==0):
        return False
    lines = lines[:-1]
    file = open(filename, "w")
    for line in lines:
        file.write(line)
    return True

def dump_log():
    copyfile("data/log", "data/dump")
    f = open("data/log", "w")
    f.close()

if(os.environ.get('DISCORD_TOKEN') == None):
    token = input("You must specify the discord bot token: ")
    os.environ['DISCORD_TOKEN'] = token

while(True):
    try:
        client.run(os.environ.get('DISCORD_TOKEN'))
    except discord.ConnectionClosed:
        print("ConnectionClosed error. Restarting")
