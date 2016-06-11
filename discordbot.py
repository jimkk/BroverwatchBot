import discord
import asyncio
import time
from gtts import gTTS
from tempfile import NamedTemporaryFile
import os

client = discord.Client()

enabled = False
message_channel = None
tts_flag = False

@client.event
@asyncio.coroutine
def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')

@client.event
@asyncio.coroutine
def on_message(message):
    global message_channel
    global tts_flag
    global enabled

    if message.content.startswith("!gogogadgetbot"):
        yield from client.send_message(message.channel, 'It\'s a me, Broverwatch Bot!')
        enabled = True
    if enabled:
        if message.content.startswith('!shutup'):
            tts_flag = False
            yield from client.send_message(message.channel, 'I will go quietly into that good night')
        elif message.content.startswith('!speakup'):
            tts_flag = True
            yield from client.send_message(message.channel, 'I will not go quietly into that good night')
        elif message.content.startswith('!joinvoice'):
            if message.author.voice_channel == None:
                yield from client.send_message(message.channel,
                message.author.mention + ' You are not in a voice channel')
            else:
                yield from client.join_voice_channel(message.author.voice_channel)
        elif message.content.startswith('!leavevoice'):
            if client.is_voice_connected(message.server):
                yield from client.voice_client_in(message.server).disconnect()
        elif message.content.startswith('!sleep'):
            yield from asyncio.sleep(5)
            yield from client.send_message(message.channel, 'Done sleeping')
        elif message.content.startswith('!goaway'):
            yield from client.send_message(message.channel, 'Ok, going away')
            enabled = False

@client.event
@asyncio.coroutine
def on_voice_state_update(before, after):
    global message_channel
    global tts_flag
    global enabled
    if enabled:
        #if(before.voice_channel == None and after.voice_channel != None and after.name != client.user.name):
        #    message = after.name + ' has joined voice channel ' + after.voice_channel.name 
        #    yield from client.send_message(after.server, message, tts=tts_flag)
        #if(before.voice_channel != None and after.voice_channel == None and before.name != client.user.name):
        #    message = before.name + ' has left voice channel ' + before.voice_channel.name
        #    yield from client.send_message(after.server, message, tts=tts_flag)
        if client.is_voice_connected(after.server):
            voice_client = client.voice_client_in(after.server)
            if voice_client.channel == after.voice_channel:
                f = NamedTemporaryFile()
                tts = gTTS(text=after.name + ' has joined the voice channel', lang='en')
                tts.save('tts.mp3')
                stream_player = voice_client.create_ffmpeg_player('tts.mp3', use_avconv=True)
                stream_player.start()
                yield from asyncio.sleep(5)
                os.remove('tts.mp3')
        if client.is_voice_connected(before.server):
            voice_client = client.voice_client_in(before.server)
            if voice_client.channel == before.voice_channel:
                #f = NamedTemporaryFile()
                print(os.path.isfile('tts.mp3'))
                while os.path.isfile('tts.mp3'):
                    print("Waiting for turn for voice")
                    yield from asyncio.sleep(4)
                tts = gTTS(text=after.name + ' has left the voice channel', lang='en')
                tts.save('tts.mp3')
                stream_player = voice_client.create_ffmpeg_player('tts.mp3', use_avconv=True)
                stream_player.start()
                yield from asyncio.sleep(1)
                os.remove('tts.mp3')

if(os.environ.get('DISCORD_TOKEN') == None):
    token = input("You must specify the discord bot token: ")
    os.environ['DISCORD_TOKEN'] = token
client.run(os.environ.get('DISCORD_TOKEN'))
