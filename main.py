import asyncio
import irc.client_aio
from jaraco.stream import buffer
import logging
import config
import aioconsole
import time 
from enum import Enum
# to do:
# get len of joined users
# 2025-04-10 12:42:06,926 DEBUG Received PUBMSG: Slot 1  Not Ready https://osu.ppy.sh/u/26964126 demi-nya        [NoFail, Easy, Hidden] from BanchoBot!cho@ppy.sh
# go through every slot get the user + mods (between [])
# set up a dictionary or enum

class Freemod_Mod_Multiplier(Enum):
    NM = 1
    Hidden = 1
    Easy = 1.7
    Hardrock = 1
    Hardrock_Hidden = 1
    Easy_Hidden = 2
    

EXPECTED_USERS = config.EXPECTED_USERS

EXPECTED_USERS = [user.replace(" ", "_") for user in EXPECTED_USERS]

BEATMAP_IDS = [bm for bm in config.BEATMAP_IDS if bm[0] != 0]
print(BEATMAP_IDS)

joined_users = []
mutli_id = 0
Current_Beatmap_Index = 0
aborted = False
votes_aborted = 0
matchongoing = False
player_mods = {}

formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

def setup_logger(name, log_file, level=logging.DEBUG):
    """To setup as many loggers as you want"""

    handler = logging.FileHandler(log_file)        
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger

logger = setup_logger('first_logger', 'logging_for_osu_multiplayer_bot.txt')

logger2 = setup_logger('second_logger', 'scores.txt')

def on_welcome(connection, event):
    logger.info(f"Connected to {connection.server}")
    connection.privmsg('BanchoBot', f"!mp make {config.multiplayer_name}")

def start_multi(connection):
    connection.privmsg(f'#mp_{mutli_id}', "!mp timer stop")
    connection.privmsg(f'#mp_{mutli_id}', "!mp start")
    if BEATMAP_IDS[Current_Beatmap_Index][1] == "TB" or BEATMAP_IDS[Current_Beatmap_Index][1] == "Freemod":
        connection.privmsg(f'#mp_{mutli_id}', "!mp settings")

def parse_pubmsg(connection, event):
    try:
        global mutli_id, joined_users, Current_Beatmap_Index, aborted, votes_aborted, matchongoing
        sender = event.source
        message = event.arguments[0]
        msgtarget = event.target
        target = str(message).split(" joined in slot")[0]
        target = target.replace(" ", "_")
        logger.debug(f"parse_pubmsg logging: sender: {sender} message: {message} event: {event}")
        logger.debug(f"Received PUBMSG: {message} from {sender}")

        if "banchobot" in str(sender).lower() and target in EXPECTED_USERS and "joined in slot" in message:
            global joined_users
            joined_users.append(target)

        if "banchobot" in str(sender).lower() and target.lower() not in EXPECTED_USERS and "joined in slot" in message:
             connection.privmsg(f'#mp_{mutli_id}', f"!mp kick {target}")

        if set(joined_users) == set(EXPECTED_USERS) and "joined in slot" in message:
            connection.privmsg(f'#mp_{mutli_id}', f"Please ready up everyone automatically starting in {config.time_between_maps} seconds")
            connection.privmsg(f'#mp_{mutli_id}', f"!mp timer {config.time_between_maps}")
            connection.privmsg(f'#mp_{mutli_id}', f"Each map everyone gets 1 time of aborting the map if half the lobby aborts the map will be auto-aborted")

        if set(joined_users) == set(EXPECTED_USERS) and "All players are ready" in message and msgtarget == f"#mp_{mutli_id}":
            matchongoing = True
            start_multi(connection)
        if "banchobot" in str(sender).lower() and "Countdown finished" in message and msgtarget == f"#mp_{mutli_id}":
            matchongoing = True
            start_multi(connection)

        sender =  str(sender).split("!")[0]
        if sender in EXPECTED_USERS and str(message).startswith(".abort") and msgtarget == f"#mp_{mutli_id}":
                votes_aborted = votes_aborted+1
                if votes_aborted >= len(EXPECTED_USERS)//2 and aborted == False and matchongoing == True:
                    votes_aborted = 0
                    aborted = True
                    connection.privmsg(f'#mp_{mutli_id}', f"!mp abort")
                    connection.privmsg(f'#mp_{mutli_id}', f"!mp timer 120")
                    print("match aborted")
                    matchongoing = False
            
        if "banchobot" in str(sender).lower() and "The match has finished" in message:
            mod_label = BEATMAP_IDS[Current_Beatmap_Index - 1][1] 
            index_in_mod = sum(1 for i in range(Current_Beatmap_Index) if BEATMAP_IDS[i][1] == mod_label)

            label = f"{mod_label if mod_label else 'NM'}{index_in_mod}"
            logger2.debug(f"above the scores for: {label}")
            if Current_Beatmap_Index < len(BEATMAP_IDS):
                beatmap_id = BEATMAP_IDS[Current_Beatmap_Index][0]
                connection.privmsg(f'#mp_{mutli_id}', f"!mp map {beatmap_id}")
                if BEATMAP_IDS[Current_Beatmap_Index][1] != "TB": # just make it freemod even if its TB
                    connection.privmsg(f'#mp_{mutli_id}', f"!mp mods 1 {BEATMAP_IDS[Current_Beatmap_Index][1]}")
                else:
                    connection.privmsg(f'#mp_{mutli_id}', f"!mp mods 1 Freemod")
                    connection.privmsg(f'#mp_{mutli_id}', f"Tiebreaker!!")
                    
                connection.privmsg(f'#mp_{mutli_id}', f"!mp timer {config.time_between_maps}")
                connection.privmsg(f'#mp_{mutli_id}', "everyone ready up for next map!")
                Current_Beatmap_Index += 1
                matchongoing = False
                aborted = False
            else:
                connection.privmsg(f'#mp_{mutli_id}', "We reached the end of the beatmap list! Thank you for joining!!")
                matchongoing = False

        if "banchobot" in str(sender).lower() and "finished playing" in message:
            score = str(message).split("Score: ")[1].split(",")[0]
            player = str(message).split(" finished playing")[0]
            player = player.replace(" ", "_")

            if BEATMAP_IDS[Current_Beatmap_Index][1] != "FreeMod" or BEATMAP_IDS[Current_Beatmap_Index][1] != "TB":
                logger2.debug(f"{player} set score: {score}")
            else:
                score = score * Freemod_Mod_Multiplier.player_mods[player].value
                logger2.debug(f"{player} set score: {score} (this is with mods)")

        if "banchobot" in str(sender).lower() and str(message).startswith("Slot"):
            player = message.split(" ")[6]
            mods = message.split("[")[1].strip().replace("]", "").split(",")

            mods = [
                mod.strip() 
                for i, mod in enumerate(mods) 
                if i != 0 and mod.strip() in Freemod_Mod_Multiplier.__members__ # thanks to ai i wouldve never gotten on this
            ]

            if mods:
                player_mods[player] = "_".join(mods)
            else:
                player_mods[player] = "NM"

    except Exception as e:
        logger.error(f"Error processing privmsg: {str(e)}")


def parse_privmsg(connection, event):
    try:
        global mutli_id, joined_users, Current_Beatmap_Index, aborted, votes_aborted, player_mods
        sender = event.source
        message = event.arguments[0]
        logger.debug(f"parse_privmsg logging: sender: {sender} message: {message} event: {event}")
        logger.debug(f"Received PRIVMSG: {message} from {sender}")
        if "banchobot" in str(sender).lower() and "Created the tournament match https://osu.ppy.sh/mp/" in message:
            mutli_id = message.split('/')[-1].split()[0]
            if mutli_id != 0:
                print(f"\nmulti id = {mutli_id}")
                global Current_Beatmap_Index
                player_mods = {}
                connection.privmsg(f'#mp_{mutli_id}', f"!mp map {BEATMAP_IDS[Current_Beatmap_Index][0]} 0")
                connection.privmsg(f'#mp_{mutli_id}', f"!mp timer {config.time_between_maps}")
                connection.privmsg(f'#mp_{mutli_id}', f"!mp set 0 3 {len(EXPECTED_USERS)}")
                for i in EXPECTED_USERS:
                    connection.privmsg(f'#mp_{mutli_id}', f"!mp invite {i}")
                connection.privmsg(f'#mp_{mutli_id}', f"!mp mods 1 {BEATMAP_IDS[Current_Beatmap_Index][1]}")
                Current_Beatmap_Index = Current_Beatmap_Index +1 # we are now passed index 0 bcuz previous was index 0 only now bcuz mods

            if "banchobot" in str(sender).lower() and "left the game" in message:
                target = str(message).split(" joined in slot")[0]
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
            server.connect(config.server, config.port, config.user, 
                         password=config.password),
            timeout=10
        )

        while True:
            datatosend = await aioconsole.ainput(f"{config.user} > ")
            server.send_raw(datatosend)
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
