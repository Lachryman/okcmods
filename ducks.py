#coding=utf8
import random
import operator

from sopel.module import commands, rule, example, event, interval
from sopel.config import ConfigurationError
from time import time
from sqlalchemy import Table, Column, String, Integer, PrimaryKeyConstraint, desc, create_engine
from sqlalchemy.schema import MetaData
from sqlalchemy.sql import select
from collections import defaultdict

duck_is_flapping = False
hunt_is_on = False
msg_stocked = 0
duck_tail = u"・゜゜・。。・゜゜"
duck = [u"\_o< ", u"\_O< ", u"\_0< ", u"\_\u00f6< ", u"\_\u00f8< ", u"\_\u00f3< "]
duck_noise = [u"QUACK!", u"FLAP FLAP!", u"quack!"]
spawn_time = 0;

metadata = MetaData()

table = Table(
    'duck_hunt',
    metadata,
    Column('name', String),
    Column('shot', Integer),
    Column('befriend', Integer),
    Column('chan', String),
    PrimaryKeyConstraint('name', 'chan')
    )

optout = Table(
    'nohunt',
    metadata,
    Column('chan', String),
    PrimaryKeyConstraint('chan')
    )





denies_friend = [

]

MSG_DELAY = 3
MASK_REQ = 10
scripters = defaultdict(int)
game_status = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
"""
game_status structure
{
  '#chan1':{
      'duck_status':0|1|2,
      'next_duck_time':'integer',
      'game_on':0|1,
      'no_duck_kick': 0|1,
      'duck_time': 'float',
      'shoot_time': 'float',
      'messages': integer,
      'masks' : list
  }
}
"""

dbEngine = None

def setup(bot):
  """load a list of channels duckhunt should be off in. Does not take networks into account"""
  global opt_out, dbEngine, metadata
  opt_out = []
  dbEngine = create_engine('sqlite:///default.db')
  metadata.create_all(dbEngine)
  chans = dbEngine.execute(select([optout.c.chan]))
  if chans:
      for row in chans:
          chan = row["chan"]
          opt_out.append(chan)

@event('JOIN', 'QUIT', 'PRIVMSG')
@rule('.*')
def incrementMsgCounter(bot, trigger):
  """Increment the number of messages said in an active game channel. Also keep track of the unique masks that are speaking."""
  global game_status
  if trigger.sender in opt_out:
    return
  if game_status[trigger.sender]['game_on'] == 1 and game_status[trigger.sender]['duck_status'] == 0:
    game_status[trigger.sender]['messages'] += 1
    if trigger.host not in game_status[trigger.sender]['masks']:
      game_status[trigger.sender]['masks'].append(trigger.host)

@commands('starthunt')
def start_hunt(bot, trigger):
  """This command starts a duckhunt in your channel, to stop the hunt use .stophunt"""
  global game_status
  if trigger.sender in opt_out:
    return
  elif not trigger.sender.startswith("#"):
    return bot.reply("No hunting by yourself, that isn't safe.")
  check = game_status[trigger.sender]['game_on']
  if check:
    return bot.reply("there is already a game running in {}.".format(trigger.sender))
  else:
    game_status[trigger.sender]['game_on'] = 1
  set_ducktime(trigger.sender)
  bot.reply("Ducks have been spotted nearby. See how many you can shoot or save. use .bang to shoot or .befriend to save them. NOTE: Ducks appear as a function of time and channel activity.", trigger.sender)

def set_ducktime(chan):
  global game_status
  game_status[chan]['next_duck_time'] = random.randint(int(time()) + 480, int(time()) + 3600)
  game_status[chan]['duck_status'] = 0
  # let's also reset the number of messages said and the list of masks that have spoken.
  game_status[chan]['messages'] = 0
  game_status[chan]['masks'] = []
  return

@commands("stophunt",)
def stop_hunt(bot, trigger):
  """This command stops the duck hunt in your channel. Scores will be preserved"""
  global game_status
  if trigger.sender in opt_out:
    return
  if game_status[trigger.sender]['game_on']:
    game_status[trigger.sender]['game_on'] = 0
    bot.reply("the game has been stopped.")
  else:
    bot.reply("There is no game running in {}.".format(trigger.sender))



@interval(11)
def deploy_duck(bot):
  global game_status
  for chan in game_status:
    active = game_status[chan]['game_on']
    duck_status = game_status[chan]['duck_status']
    next_duck = game_status[chan]['next_duck_time']
    chan_messages = game_status[chan]['messages']
    chan_masks = game_status[chan]['masks']
    if active == 1 and duck_status == 0 and next_duck <= time() and chan_messages >= MSG_DELAY and len(chan_masks) >= MASK_REQ:
      #deploy a duck to channel
      game_status[chan]['duck_status'] = 1
      game_status[chan]['duck_time'] = time()
      dtail, dbody, dnoise = generate_duck()
      bot.say(u'{}{}{} '.format(dtail, dbody, dnoise), chan)
    continue

def generate_duck():
  """Try and randomize the duck message so people can't highlight on it/script against it."""
  rt = random.randint(1, len(duck_tail) - 1)
  dtail = duck_tail[:rt] + u' \u200b ' + duck_tail[rt:]
  dbody = random.choice(duck)
  rb = random.randint(1, len(dbody) - 1)
  dbody = dbody[:rb] + u'\u200b' + dbody[rb:]
  dnoise = random.choice(duck_noise)
  rn = random.randint(1, len(dnoise) - 1)
  dnoise = dnoise[:rn] + u'\u200b' + dnoise[rn:]
  return (dtail, dbody, dnoise)

def hit_or_miss(deploy, shoot):
  """This function calculates if the befriend or bang will be successful."""
  if shoot - deploy < 1:
    return .05
  elif 1 <= shoot - deploy <= 7:
    out = random.uniform(.60, .75)
    return out
  else:
    return 1

def dbadd_entry(nick, chan, shoot, friend):
  """Takes care of adding a new row to the database."""
  query = table.insert().values(
    chan = chan.lower(),
    name = nick,
    shot = shoot,
    befriend = friend)
  dbEngine.execute(query)

def dbupdate(nick, chan, shoot, friend):
  """update a db row"""
  if shoot and not friend:
    query = table.update() \
      .where(table.c.chan == chan.lower()) \
      .where(table.c.name == nick) \
      .values(shot = shoot)
    dbEngine.execute(query)
  elif friend and not shoot:
    query = table.update() \
      .where(table.c.chan == chan.lower()) \
      .where(table.c.name == nick) \
      .values(befriend = friend)
    dbEngine.execute(query)
  elif friend and shoot:
    query = table.update() \
      .where(table.c.chan == chan.lower()) \
      .where(table.c.name == nick) \
      .values(befriend = friend) \
      .values(shot = shoot)
    dbEngine.execute(query)

@commands("bang")
def bang(bot, trigger):
  """when there is a duck on the loose use this command to shoot it."""
  global game_status, scripters
  chan = trigger.sender
  nick = trigger.nick
  if chan in opt_out:
      return
  score = ""
  out = ""
  miss = [
    "WHOOSH! You missed the duck completely!",
    "Your gun jammed!",
    "Better luck next time.",
    "WTF!? Who are you Dick Cheney?",
    'Meat is murder!',
    u'"I have a boyfriend!" — the duck.'
  ]
  if not game_status[chan]['game_on']:
    bot.reply("There is no activehunt right now. Use .starthunt to start a game.")
  elif game_status[chan]['duck_status'] != 1:
    bot.reply("There is no duck. What are you shooting at?")
  else:
    game_status[chan]['shoot_time'] = time()
    deploy = game_status[chan]['duck_time']
    shoot = game_status[chan]['shoot_time']
    if nick in scripters:
      if scripters[nick] > shoot:
        bot.notice("You are in a cool down period, you can try again in {} seconds.".format(str(scripters[nick] - shoot)))
        return
    chance = hit_or_miss(deploy, shoot)
    if not random.random() <= chance and chance > .05:
      out = random.choice(miss) + " You can try again in 7 seconds."
      scripters[nick] = shoot + 7
      return bot.reply(out)
    if chance == .05:
      out += "You pulled the trigger in {} seconds, that's mighty fast. Are you sure you aren't a script? Take a 2 hour cool down.".format(str(shoot - deploy))
      scripters[nick] = shoot + 7200
      if not random.random() <= chance:
        return bot.reply(random.choice(miss) + " " + out)
      else:
        return bot.reply(out)
    game_status[chan]['duck_status'] = 2
    score = dbEngine.execute(select([table.c.shot]) \
      .where(table.c.chan == chan.lower()) \
      .where(table.c.name == nick)).fetchone()
    if score:
      score = score[0]
      score += 1
      dbupdate(nick, chan, score, 0)
    else:
      score = 1
      dbadd_entry(nick, chan, score, 0)
    timer = "{:.3f}".format(shoot - deploy)
    duck = "duck" if score == 1 else "ducks"
    bot.reply("you shot a duck in {} seconds! You have killed {} {} in {}.".format(timer, score, duck, chan))
    set_ducktime(chan)

@commands("bef")
def bef(bot, trigger):
  """when there is a duck on the loose use this command to shoot it."""
  global game_status, scripters
  chan = trigger.sender
  nick = trigger.nick
  if chan in opt_out:
      return
  score = ""
  out = ""
  miss = [
    u"The duck didn't want to be friends, maybe next time.",
    u"Well this is awkward, the duck needs to think about it.",
    u"The duck said no, maybe bribe it with some pizza? Ducks love pizza don't they?",
    u"Who knew ducks could be so picky?",
    u'The duck knows about your browser history. Why do you follow u/fucksWithDucks?',
    u'Your reputation precedes you. The duck doesn\'t want to be alone with you.',
    u'"I have been burned before, how do I know I can trust you?" - the duck.'
  ]
  if not game_status[chan]['game_on']:
    bot.reply("There is no activehunt right now. Use .starthunt to start a game.")
  elif game_status[chan]['duck_status'] != 1:
    bot.reply("You tried befriending a non-existent duck, that's fucking creepy.")
  else:
    game_status[chan]['shoot_time'] = time()
    deploy = game_status[chan]['duck_time']
    shoot = game_status[chan]['shoot_time']
    if nick in scripters:
      if scripters[nick] > shoot:
        bot.notice("You are in a cool down period, you can try again in {} seconds.".format(str(scripters[nick] - shoot)))
        return
    chance = hit_or_miss(deploy, shoot)
    if not random.random() <= chance and chance > .05:
      out = random.choice(miss) + " You can try again in 7 seconds."
      scripters[nick] = shoot + 7
      return bot.reply(out)
    if chance == .05:
      out += "You tried friending that duck in {} seconds, that's mighty fast. Are you sure you aren't a script? Take a 2 hour cool down.".format(str(shoot - deploy))
      scripters[nick] = shoot + 7200
      if not random.random() <= chance:
        return bot.reply(random.choice(miss) + " " + out)
      else:
        return bot.reply(out)
    game_status[chan]['duck_status'] = 2
    score = dbEngine.execute(select([table.c.befriend]) \
      .where(table.c.chan == chan.lower()) \
      .where(table.c.name == nick)).fetchone()
    if score:
      score = score[0]
      score += 1
      dbupdate(nick, chan, 0, score)
    else:
      score = 1
      dbadd_entry(nick, chan, 0, score)
    timer = "{:.3f}".format(shoot - deploy)
    duck = "duck" if score == 1 else "ducks"
    bot.reply("you befriended a duck in {} seconds! You have made friends with {} {} in {}.".format(timer, score, duck, chan))
    set_ducktime(chan)


def smart_truncate(content, length=320, suffix='...'):
  if len(content) <= length:
    return content
  else:
    return content[:length].rsplit(' • ', 1)[0]+suffix

@commands("killers")
def killers(bot, trigger):
  """Prints a list of the top duck killers in the channel, if 'global' is specified all channels in the database are included."""
  chan = trigger.sender
  if chan in opt_out:
    return
  killers = defaultdict(int)
  chancount = defaultdict(int)
  out = ""
  text = trigger.group(2) or ""
  if text.lower() == 'global' or text.lower() == 'average':
    out = "Duck killer scores across the network: "
    scores = dbEngine.execute(select([table.c.name, table.c.shot]) \
      .order_by(desc(table.c.shot)))
    if scores:
      for row in scores:
        if row[1] == 0:
            continue
        chancount[row[0]] += 1
        killers[row[0]] += row[1]
      if text.lower() == 'average':
        for k, v in killers.items():
          killers[k] = int(v / chancount[k])
    else:
      return bot.reply("it appears no one has killed any ducks yet.")
  else:
    out = "Duck killer scores in {}: ".format(chan)
    scores = dbEngine.execute(select([table.c.name, table.c.shot]) \
      .where(table.c.chan == chan.lower()) \
      .order_by(desc(table.c.shot)))
    if scores:
      for row in scores:
        if row[1] == 0:
          continue
        killers[row[0]] += row[1]
    else:
      return bot.reply("it appears no one has killed any ducks yet.")

  topkillers = sorted(killers.items(), key=operator.itemgetter(1), reverse = True)
  out += u' • '.join([u"{}: {}".format(k, str(v))  for k, v in topkillers])
  out = smart_truncate(out)
  return bot.reply(out)

@commands("friends")
def friends(bot, trigger):
  """Prints a list of the top duck friends in the channel, if 'global' is specified all channels in the database are included."""
  chan = trigger.sender
  if chan in opt_out:
    return
  friends = defaultdict(int)
  chancount = defaultdict(int)
  out = ""
  text = trigger.group(2) or ""
  if text.lower() == 'global' or text.lower() == 'average':
    out = "Duck friends scores across the network: "
    scores = dbEngine.execute(select([table.c.name, table.c.befriend]) \
      .order_by(desc(table.c.befriend)))
    if scores:
      for row in scores:
        if row[1] == 0:
            continue
        chancount[row[0]] += 1
        friends[row[0]] += row[1]
      if text.lower() == 'average':
        for k, v in friends.items():
          friends[k] = int(v / chancount[k])
    else:
      return bot.reply("it appears no one has friended any ducks yet.")
  else:
    out = "Duck friends scores in {}: ".format(chan)
    scores = dbEngine.execute(select([table.c.name, table.c.befriend]) \
      .where(table.c.chan == chan.lower()) \
      .order_by(desc(table.c.befriend)))
    if scores:
      for row in scores:
        if row[1] == 0:
          continue
        friends[row[0]] += row[1]
    else:
      return bot.reply("it appears no one has friended any ducks yet.")

  topfriends = sorted(friends.items(), key=operator.itemgetter(1), reverse = True)
  out += u' • '.join([u"{}: {}".format(k, str(v))  for k, v in topfriends])
  out = smart_truncate(out)
  return bot.reply(out)

@commands("ducks")
def ducks_user(bot, trigger):
  """Prints a users duck stats. If no nick is input it will check the calling username."""
  name = trigger.group(2) or trigger.nick
  ducks = defaultdict(int)
  chan = trigger.sender
  scores = dbEngine.execute(select([table.c.name, table.c.chan, table.c.shot, table.c.befriend])
    .where(table.c.name == name)).fetchall()
  if scores:
    for row in scores:
      if row["chan"].lower() == chan.lower():
        ducks["chankilled"] += row["shot"]
        ducks["chanfriends"] += row["befriend"]
      ducks["killed"] += row["shot"]
      ducks["friend"] += row["befriend"]
      ducks["chans"] += 1
    if ducks["chans"] == 1:
      return bot.say(u"{} has killed {} and befriended {} ducks in {}.".format(name, ducks["chankilled"], ducks["chanfriends"], chan))
    kill_average = int(ducks["killed"] / ducks["chans"])
    friend_average = int(ducks["friend"] / ducks["chans"])
    message(u"\x02{}'s\x02 duck stats: \x02{}\x02 killed and \x02{}\x02 befriended in {}. Across {} channels: \x02{}\x02 killed and \x02{}\x02 befriended. Averaging \x02{}\x02 kills and \x02{}\x02 friends per channel.".format(name, ducks["chankilled"], ducks["chanfriends"], chan, ducks["chans"], ducks["killed"], ducks["friend"], kill_average, friend_average))
  else:
      return u"It appears {} has not participated in the duck hunt.".format(name)
