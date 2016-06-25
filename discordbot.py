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
>!bbwiki <searchterm>    -    Links the Overwatch Wikipage for <searchterm>"""

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

    if(message.author.id in blacklist):
        #nothing should happen if a user is in the blacklist
        if (message.content.startswith('!bb')):
            #yield from client.send_message(message.channel, message.author.mention + "https://giphy.com/gifs/naru-13r5cLwRjhteQE")
            print(message.author.name + " tried to say \""+message.content+"\" but is blacklisted")
        return
    elif (message.content.startswith('!gogogadgetbot') or message.content.startswith('!bbon')):
        yield from client.send_message(message.channel, 'It\'s a me, Broverwatch Bot!')
        enabled = True
    elif (message.content.startswith('!bbhelp') or message.content.startswith('!bb ') or message.content == '!bb'):
            yield from client.send_message(message.channel, helpmsg)
    elif enabled:
        if message.content.startswith('!bbsay'):
            yield from say(message)        
        elif (message.content.startswith('!shutup') or message.content.startswith('!bbmute')):
            tts_flag = False
            yield from client.send_message(message.channel, 'I will go quietly into that good night')
        elif (message.content.startswith('!speakup') or message.content.startswith('!bbunmute')):
            tts_flag = True
            yield from client.send_message(message.channel, 'I will not go quietly into that good night')
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
                yield from client.join_voice_channel(message.author.voice_channel)
        elif (message.content.startswith('!leavevoice') or message.content.startswith('!bbleave')):
            if client.is_voice_connected(message.server):
                yield from client.voice_client_in(message.server).disconnect()
        elif (message.content.startswith('!goaway') or message.content.startswith('!bboff')):
            yield from client.send_message(message.channel, 'Ok, going away')
            enabled = False
        elif (message.content.startswith('!bbmyson')):
            yield from client.send_message(message.channel, 'Overwatch: \n' + listlines("res/audioclips/ow"))
            yield from client.send_message(message.channel, 'Wow: \n' + listlines("res/audioclips/wow"))
            yield from client.send_message(message.channel, 'Hearthstone: \n' + listlines("res/audioclips/hs"))
        elif (message.content.startswith('!bbcleanup')):
            yield from cleanup(message)
        elif (message.content.startswith('!bbcowsay')):
            yield from bbcowsay(message)
        elif (message.content.startswith('!bbwiki')):
            yield from wikisearch(message)
        elif message.content.startswith('!bbsetadminchannel') and admin_channel == None:
            set_admin_channel(message.channel)
            yield from client.send_message(message.channel, 'This channel is now the admin channel') 
        elif message.channel.id == admin_channel and message.content.startswith('!bbblacklist'):
            username = message.content.split(" ")[1]
            added = add_to_blacklist(username)
            if added:
                yield from client.send_message(message.channel, "Added " +  username + " to blacklist")
            else:
                yield from client.send_message(message.channel, "Removed " +  username + " from blacklist")

@client.event
@asyncio.coroutine
def on_voice_state_update(before, after):
    global message_channel
    global tts_flag
    global enabled
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
    if message.content.startswith('!bbsay'): #remove bbsay commands
        return True
    elif message.content.startswith('Voice clip not found. RIP.'): #remove failed bbsay responses
        return True
    elif message.content.startswith('Please give a voice line:'): #remove failed bbsay responses
        return True
    elif message.content.startswith(' COMMAND LIST:'): #remove bb / bbhelp responses
        return True
    elif message.content.startswith('!bb ') or message.content == '!bb' or message.content.startswith('!bbhelp'): #remove bbhelp and bb commands
        return True
    elif message.content.startswith('!bbcleanup'): #remove bbcleanup commands
        return True
    elif message.content.startswith('!bbmyson'): #remove bbmyson commands
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

if(os.environ.get('DISCORD_TOKEN') == None):
    token = input("You must specify the discord bot token: ")
    os.environ['DISCORD_TOKEN'] = token

while(True):
    try:
        client.run(os.environ.get('DISCORD_TOKEN'))
    except ConnectionClosed:
        print("ConnectionClosed error. Restarting")
