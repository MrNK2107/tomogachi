"""Brutal placement reality check & savage roast bank."""

import random
from typing import Optional

# -------------------------------------------------------------------------
# ROASTS: WHEN LAPTOP IS IDLE & NO AGENT IS RUNNING (DOOMSCROLLING ON PHONE)
# -------------------------------------------------------------------------

LEVEL_1_ROASTS = [
    (
        "📱 *PUT THE PHONE DOWN, YOU CLOWN.* 🤡\n\n"
        "Your laptop has been sitting untouched for 15 minutes with ZERO tasks running.\n"
        "I know exactly what you're doing right now — lying back, scrolling Instagram Reels or YouTube Shorts like you've already cracked Google.\n\n"
        "Newsflash: The guy you're competing against for that 25 LPA package just solved 2 Hard graph problems while you watched a 30-second video of someone else living your dream life.\n\n"
        "Put the phone face down and get back to your desk."
    ),
    (
        "🚨 *BUSTED. What are you looking at on your phone?* 🤨\n\n"
        "15 minutes of absolute zero productivity on your laptop.\n"
        "Are you reading documentation? No.\n"
        "Are you solving LeetCode? No.\n"
        "You're staring at a 6-inch glass screen rotting your dopamine receptors while placement season is knocking at your door.\n\n"
        "Companies are not going to ask you about trending memes in the technical interview. Get back to work."
    ),
    (
        "💀 *Zero code written. Zero agents running. 100% doomscrolling.* 📱\n\n"
        "You really thought you could step away from your laptop and nobody would notice?\n"
        "You have placement rounds coming up and your resume has 2 copied projects and a prayer.\n"
        "Do you want an actual tech job or are you mentally preparing for a mass-recruiter aptitude rejection email?\n\n"
        "Sit up straight, drop the phone, and open your IDE."
    )
]

LEVEL_2_ROASTS = [
    (
        "🔥 *30+ MINUTES GONE. Are you seriously still on your phone?!* 🤦‍♂️\n\n"
        "Half an hour of your life flushed down the toilet.\n"
        "While you're sitting there mindlessly flicking your thumb across the screen, 50,000 other candidates just practiced their SQL joins, OS paging concepts, and dynamic programming.\n\n"
        "Every single minute you waste on that phone lowers your starting salary by 10%. Keep scrolling if you love unemployment."
    ),
    (
        "📉 *BREAKING: Local student chooses Instagram over a career.* 📰\n\n"
        "You've been idle for over 30 minutes. No agent running. No compilation. Just pure, unadulterated procrastination.\n\n"
        "You can't even explain the difference between a Process and a Thread right now without stuttering, but you know every viral audio on the internet.\n\n"
        "Get off your bed. Walk back to your laptop. Right now."
    ),
    (
        "☠️ *The Technical Round Interviewer is going to eat you alive.* 🥩\n\n"
        "You think placements are a joke? You think luck is going to carry you through 3 rounds of DSA and System Design?\n"
        "You couldn't even stay focused at your desk for 30 minutes before reaching for your phone like an addict.\n\n"
        "Your competition isn't scrolling reels. They are grinding. Put that phone down before it ruins your career."
    )
]

LEVEL_3_ROASTS = [
    (
        "🚨 *MAXIMUM EMERGENCY: 45+ MINUTES OF PURE TIME WASTING.* 🛑\n\n"
        "Look at yourself. Seriously, look at your reflection in that black phone screen right now.\n"
        "Is this who you wanted to be? The person who makes big plans in the morning and spends the entire day scrolling brainrot?\n\n"
        "Tomorrow you'll complain that 'the market is bad' and 'hiring is frozen'. The market isn't frozen, YOUR WORK ETHIC IS.\n\n"
        "THROW THE PHONE ACROSS THE ROOM AND SIT IN FRONT OF YOUR LAPTOP."
    ),
    (
        "⚰️ *R.I.P. to your dream company offer letter.* 🪦\n\n"
        "You just wasted nearly an hour doing absolutely nothing of value.\n"
        "Your laptop screen is probably turned off from sheer boredom while you're glued to mobile notifications.\n\n"
        "If you don't get back to your laptop in the next 60 seconds, don't act surprised when placement results come out and your name isn't on the list."
    )
]

# -------------------------------------------------------------------------
# SHUTDOWN / SLEEP / LID CLOSED ROASTS
# -------------------------------------------------------------------------

SHUTDOWN_LID_ROASTS = [
    (
        "🚪 *CLOSING YOUR LAPTOP ALREADY?! ARE YOU KIDDING ME?!* 🤡\n\n"
        "Lid closed / sleep mode detected.\n"
        "Did you actually accomplish anything today or did you just warm up your chair?\n\n"
        "You're about to crawl into bed with your phone and scroll for the next 2 hours, aren't you?\n"
        "Your competition is staying up solving DP on Trees and you just put your laptop to sleep like you've already secured the offer.\n\n"
        "OPEN THAT LAPTOP BACK UP AND EARN YOUR REST."
    ),
    (
        "⚠️ *LAPTOP SHUTTING DOWN / SLEEPING.* 😴\n\n"
        "Giving up already? That was quick.\n"
        "Hope you have a backup plan for placements because 45 minutes of half-hearted effort isn't getting you past the first online assessment.\n\n"
        "If you're turning off your machine to stare at your phone in bed, you're only lying to yourself.\n"
        "Solve at least ONE LeetCode problem on your phone right now before you sleep."
    ),
    (
        "💤 *Sleep mode activated? More like career snooze activated.* 📉\n\n"
        "You just shut down your workstation.\n"
        "Ask yourself honestly: Did you outwork your competition today?\n"
        "If the answer is No, don't touch your phone for entertainment tonight. Go open a technical book or review DSA notes."
    )
]

def get_brutal_roast(idle_minutes: float) -> str:
    """Returns a brutally savage roast calibrated to the duration of phone doomscrolling."""
    if idle_minutes >= 45:
        return random.choice(LEVEL_3_ROASTS)
    elif idle_minutes >= 30:
        return random.choice(LEVEL_2_ROASTS)
    else:
        return random.choice(LEVEL_1_ROASTS)

def get_shutdown_roast() -> str:
    """Returns a merciless roast when the laptop is closed, put to sleep, or shut down."""
    return random.choice(SHUTDOWN_LID_ROASTS)
