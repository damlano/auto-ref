import asyncio
import irc.client_aio
import autoref
from jaraco.stream import buffer
import logging
import time

EXPECTED_USERS = ["demi-nya"]

EXPECTED_USERS = [user.replace(" ", "_") for user in EXPECTED_USERS]

BEATMAP_IDS = [
    (4385400, "DT"), 
    (4899851, "HD")
]

joined_users = []
mutli_id = 0
Current_Beatmap_Index = 0
# to do
leftduringmap = []
mapstarttime = 0
mapendtime = 0

logname = "logging_for_osu_multiplayer_bot.txt"

logging.basicConfig(filename=logname,
                    filemode='a',
                    format='%(asctime)s,%(msecs)03d %(name)s %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.DEBUG)

logger = logging.getLogger(__name__)
logging.getLogger("irc.client_aio").setLevel(logging.DEBUG)

def on_welcome(connection, event):
    logger.info(f"Connected to {connection.server}")
    connection.privmsg('BanchoBot', "!mp make meow")

def start_multi(connection):
    connection.privmsg(f'#mp_{mutli_id}', "!mp start")

def parse_pubmsg(connection, event):
    try:
        sender = event.source
        message = event.arguments[0]
        target = str(message).split(" j")[0]
        target = target.replace(" ", "_")

        if "banchobot" in str(sender).lower() and target in EXPECTED_USERS and "joined in slot" in message:
            global joined_users
            joined_users.append(target)

        if "banchobot" in str(sender).lower() and target not in EXPECTED_USERS and "joined in slot" in message:
             connection.privmsg(f'#mp_{mutli_id}', f"!mp kick {target}")

        if set(joined_users) == set(EXPECTED_USERS) and "joined in slot" in message:
            connection.privmsg(f'#mp_{mutli_id}', "Please ready up everyone automatically starting in 60 seconds")
            connection.privmsg(f'#mp_{mutli_id}', "!mp timer 60")

        if set(joined_users) == set(EXPECTED_USERS) and "All players are ready" in message:
            connection.privmsg(f'#mp_{mutli_id}', "!mp timer stop")
            connection.privmsg(f'#mp_{mutli_id}', "!mp start")

        if "banchobot" in str(sender).lower() and "Countdown finished" in message:
            connection.privmsg(f'#mp_{mutli_id}', "!mp start")
            
        if "banchobot" in str(sender).lower() and "The match has finished" in message:
            global Current_Beatmap_Index
            if Current_Beatmap_Index < len(BEATMAP_IDS):
                beatmap_id = BEATMAP_IDS[Current_Beatmap_Index][0]
                connection.privmsg(f'#mp_{mutli_id}', f"!mp map {beatmap_id}")
                connection.privmsg(f'#mp_{mutli_id}', f"!mp mods 1 {BEATMAP_IDS[Current_Beatmap_Index][1]}")
                connection.privmsg(f'#mp_{mutli_id}', "!mp timer 60")
                connection.privmsg(f'#mp_{mutli_id}', "everyone ready up for next map!")
                Current_Beatmap_Index += 1
            else:
                connection.privmsg(f'#mp_{mutli_id}', "We reached the end of the beatmap list! Thank you for joining!!")

    except Exception as e:
        logger.error(f"Error processing privmsg: {str(e)}")


def parse_privmsg(connection, event):
    try:
        sender = event.source
        message = event.arguments[0]
        logger.debug(f"parse_privmsg logging: sender: {sender} message: {message} event: {event}")
        logger.debug(f"Received PRIVMSG: {message} from {sender}")

        if "banchobot" in str(sender).lower() and "Created the tournament match https://osu.ppy.sh/mp/" in message:
            global mutli_id
            mutli_id = message.split('/')[-1].split()[0]
            if mutli_id != 0:
                global Current_Beatmap_Index
                connection.privmsg(f'#mp_{mutli_id}', f"!mp map {BEATMAP_IDS[Current_Beatmap_Index][0]} 0")
                connection.privmsg(f'#mp_{mutli_id}', "!mp timer 60")
                connection.privmsg(f'#mp_{mutli_id}', f"!mp set 0 3 {len(EXPECTED_USERS)}")
                for i in EXPECTED_USERS:
                    connection.privmsg(f'#mp_{mutli_id}', f"!mp invite {i}")
                connection.privmsg(f'#mp_{mutli_id}', f"!mp mods 1 {BEATMAP_IDS[Current_Beatmap_Index][1]}")
                Current_Beatmap_Index = Current_Beatmap_Index +1 # we are now passed index 0 bcuz previous was index 0 only now bcuz mods

            if "banchobot" in str(sender).lower() and "left the game" in message:
                target = str(message).split(" j")[0]
                target = target.replace(" ", "_")
                global joined_users
                joined_users.remove(target)

    except Exception as e:
        logger.error(f"Error processing privmsg: {str(e)}")

async def main():

    loop = asyncio.get_event_loop()
    
    client = irc.client_aio.AioReactor(loop=loop)
    server = client.server()
    server.buffer_class = buffer.LenientDecodingLineBuffer
    
    try:
        server.add_global_handler("motdstart", on_welcome)
        server.add_global_handler("privmsg", parse_privmsg)
        server.add_global_handler("pubmsg", parse_pubmsg)
        logger.debug("Event handlers registered")
        await asyncio.wait_for(
            server.connect(autoref.server, autoref.port, autoref.user, 
                         password=autoref.passwd),
            timeout=10
        )
        
        while True:
            await asyncio.sleep(1)
            
    except ConnectionRefusedError:
        logger.error("Connection refused. Check server details.")
    except TimeoutError:
        logger.error("Connection timed out.")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
    finally:
        if 'server' in locals() and server.is_connected():
            print(f"HELLO THIS WAS THE MULTI: {mutli_id}")
            server.privmsg(f'#mp_{mutli_id}', "!mp close")
            server.disconnect("Shutting down...")

if __name__ == "__main__":
    asyncio.run(main())