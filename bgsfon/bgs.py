import requests
import json
import sqlite3
import os.path
import time
import datetime
import sys
import shutil
from collections import defaultdict
import itertools
from math import sqrt
try:
  from . import db
except:
  pass

EXPANSION_RADIUS = 27.5
EXPANSION_THRESHOLD = 0.65
EXPANSION_FACTION_THRESHOLD = 6
RETREAT_THRESHOLD = 0.05
WAR_THRESHOLD = 0.05
TICK_TIME = "15:30:00"
TIME_FORMAT = '%d-%m-%Y %H:%M:%S'
DEBUG_LEVEL = 0
LOCAL_JSON_PATH = "LOCAL_JSON"
DATABASE = "bgs-data.sqlite3"
conn = None

def distance(p0,p1):
  x0,y0,z0 = p0
  x1,y1,z1 = p1
  return abs(sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2 + (z1 - z0) ** 2))

def debug(message,level = 0):
  if level <= DEBUG_LEVEL:
    print(message)

def clean_local_json_path():
  if os.path.exists(LOCAL_JSON_PATH):
    shutil.rmtree(LOCAL_JSON_PATH)

def get_local_json_path(filename):
  if not os.path.exists(LOCAL_JSON_PATH):
    os.mkdir(LOCAL_JSON_PATH)
  return "/".join((LOCAL_JSON_PATH,filename))

def get_json_data(filename,request, request_data, local = False):
  data = None
  json_file_path = get_local_json_path(filename)
  if local and os.path.isfile(json_file_path):
      json_file = open(json_file_path,"r")
      data = json.load(json_file)
  else:
    r = requests.post(request, request_data)
    data = json.loads(r.text)
    if r.text == "[]":
      print(r.headers)
      exit(-1)
    json_file = open(json_file_path,"w")
    json_file.write(json.dumps(data))
    json_file.close()
  return data

def get_db_connection():
  global conn
  if not conn:
    conn = sqlite3.connect(DATABASE)
  return conn

def fetch_system(systemName):
  conn = get_db_connection()
  c = conn.cursor()
  c.execute("SELECT * FROM Systems WHERE system_name=:name",{'name':systemName})
  data = c.fetchone()
  return data

def fetch_faction(factionName):
  conn = get_db_connection()
  c = conn.cursor()
  c.execute("SELECT * FROM Factions WHERE faction_name=:name",{'name':factionName})
  data = c.fetchone()
  return data

def fill_factions_from_system(systemName, local = False):
  conn = get_db_connection()
  c = conn.cursor()
  data_factions = get_json_data("factions_{0}.json".format(systemName),
                       "https://www.edsm.net/api-system-v1/factions",
                       {'systemName': systemName, 'showHistory':1}, 
                       local)
  if not data_factions['factions']:
    return None
  for faction in data_factions['factions']:
    if not fetch_faction(faction['name']):
      values = [faction['name'],faction['allegiance'],faction['government'],faction['isPlayer'], None]
      c.execute("INSERT INTO Factions VALUES (?,?,?,?,?)",values)
  conn.commit()    

def fill_systems_in_bubble(systemName, radius = EXPANSION_RADIUS, local = False): 
  conn = get_db_connection()
  c = conn.cursor()
  debug("RADIUS:",radius)
  data_bubble = get_json_data("sphere_{0}.json".format(systemName),
                       "https://www.edsm.net/api-v1/sphere-systems",
                       {'systemName': systemName,'radius':radius}, 
                       local)
  for system in data_bubble:
    distance = system['distance']
    data_system = get_json_data("system_{0}.json".format(system['name']),
                   "https://www.edsm.net/api-v1/system",
                   {'systemName': system['name'],'showPrimaryStar':1,'showInformation':1,"showCoordinates":1}, 
                   local)
    population = 0
    economy = 'None'
    
    if data_system['information']:
      x,y,z = (0,0,0)
      if data_system['coords']:
        x,y,z = data_system['coords']['x'],data_system['coords']['y'],data_system['coords']['z']
      population = data_system['information']['population']
      economy = data_system['information']['economy']
      allegiance = data_system['information']['allegiance']
      faction = data_system['information']['faction']
      factionState = data_system['information']['factionState']
      values = [data_system['name'],
                population,
                economy,distance,allegiance,faction,factionState,x,y,z] 
      try:
        c.execute("INSERT INTO Systems VALUES (?,?,?,?,?,?,?,?,?,?)",values)
      except sqlite3.IntegrityError:
        pass
    data_stations = get_json_data("stations_{0}.json".format(system['name']),
                     "https://www.edsm.net/api-system-v1/stations",
                     {'systemName': system['name']}, 
                     local)
    for station in data_stations['stations']:
      controlling_faction = None
      if 'controllingFaction' in station:
        controlling_faction = station['controllingFaction']['name']
      values = [systemName,station['name'],station['type'],station['distanceToArrival'],station['economy'],controlling_faction]
      try:
        c.execute("INSERT INTO Stations VALUES (?,?,?,?,?,?)",values)
      except sqlite3.IntegrityError:
        pass
    debug("Updating system: {0}".format(system['name']))
    fill_factions_from_system(data_system['name'], local)
  conn.commit()

def fetch_systems(criteria = None):
    conn = get_db_connection()
    c = conn.cursor()
    if criteria:
      c.execute("SELECT * FROM Systems WHERE {0}".format(criteria))
    else:
      c.execute("SELECT * FROM Systems")  
    return c.fetchall()

def clean_updates():
  conn = get_db_connection()
  c = conn.cursor()
  c.execute("DELETE FROM ticks")
  c.execute("DELETE FROM faction_system")
  c.execute("DELETE FROM system_status")
  c.execute("DELETE FROM faction_system_state")
  conn.commit()

def clean_fixed_tables():
  conn = get_db_connection()
  c = conn.cursor()
  c.execute("DELETE FROM Factions")
  c.execute("DELETE FROM Systems")
  c.execute("DELETE FROM Stations")
  conn.commit()

def get_time(cur_time = None):
  current_time = time.time()
  if cur_time != None:
    if isinstance(cur_time,str):
      current_time = get_epoch_from_utc_time(cur_time)
    elif isinstance(cur_time,float) or isinstance(cur_time,int):
      current_time = cur_time
    else:
      print("DATE FORMAT ERROR")
      exit(-1)
  return current_time

def get_last_tick_time(cur_time = None):
  current_time = get_time(cur_time)
  
  todays_tick_time = get_todays_tick_time(current_time)
  if current_time >= todays_tick_time:
    return todays_tick_time
  else:
    todays_tick_datetime = datetime.datetime.fromtimestamp(todays_tick_time)
    tomorrows_tick_datetime = todays_tick_datetime - datetime.timedelta(days=1)
    return tomorrows_tick_datetime.timestamp()
    
def get_next_tick_time(cur_time = None):
  current_time = get_time(cur_time)
  
  todays_tick_time = get_todays_tick_time(current_time)
  if current_time < todays_tick_time:
    return todays_tick_time
  else:
    todays_tick_datetime = datetime.datetime.fromtimestamp(todays_tick_time)
    tomorrows_tick_datetime = todays_tick_datetime + datetime.timedelta(days=1)
    return tomorrows_tick_datetime.timestamp()

def get_current_tick_time(cur_time = None):
  current_time = get_time(cur_time)
  
  todays_tick_time = get_todays_tick_time(current_time)
  last_tick_time = get_last_tick_time(current_time)
  if current_time <= todays_tick_time:
    return last_tick_time
  else:
    return todays_tick_time    
  
def get_todays_tick_time(cur_time = None):
  current_time = get_time(cur_time)
  
  day_time = time.strftime("%d-%m-%Y",time.gmtime(current_time))
  if cur_time:
    day_time = time.strftime("%d-%m-%Y",time.gmtime(cur_time))
  todays_tick_time = " ".join((day_time,TICK_TIME))
  return get_epoch_from_utc_time(todays_tick_time)

def is_update_needed(conn,cur_time = None):
  current_time = time.time()
  if cur_time:
    if isinstance(cur_time,str):
      current_time = get_epoch_from_utc_time(cur_time)
    elif isinstance(cur_time,float) or isinstance(cur_time,int):
      current_time = cur_time
    else:
      print("DATE FORMAT ERROR")
      return False
  last_update_time = get_last_update(conn)
  todays_tick_time = get_todays_tick_time(current_time)
  current_tick_time = get_current_tick_time(current_time)
  next_tick_time = get_next_tick_time(current_time)
  debug("CURRENT_TIME:\t\t{0} [{1}]".format(int(current_time),get_utc_time_from_epoch(current_time)))
  debug("LAST_UPDATE_TIME:\t{0} [{1}]".format(int(last_update_time),get_utc_time_from_epoch(last_update_time)))
  debug("TODAYS_TICK_TIME:\t{0} [{1}]".format(int(todays_tick_time),get_utc_time_from_epoch(todays_tick_time)))
  debug("CURRENT_TICK_TIME:\t{0} [{1}]".format(int(current_tick_time),get_utc_time_from_epoch(current_tick_time)))
  debug("NEXT_TICK_TIME:\t\t{0} [{1}]".format(int(next_tick_time),get_utc_time_from_epoch(next_tick_time)))

  if last_update_time == 0:
    return True
  if current_time > last_update_time and last_update_time < todays_tick_time: 
    if current_time < todays_tick_time:
      return False
    else:
      return True
  else:
    return False

def get_utc_time_from_epoch(epoch):
  if isinstance(epoch,str):
    epoch = int(epoch)
  return time.strftime(TIME_FORMAT,time.gmtime(epoch))

def get_epoch_from_utc_time(utc_time):
  return time.mktime(time.strptime(utc_time, TIME_FORMAT))

def get_timestamp(cur_time = None):
  current_time = time.time()
  if cur_time:
    if isinstance(cur_time,str):
      current_time = get_epoch_from_utc_time(cur_time)
    elif isinstance(cur_time,float) or isinstance(cur_time,int):
      current_time = cur_time
    else:
      print("DATE FORMAT ERROR")
      exit(-1)
  return int(current_time)

def time_functions_test():
  for test_check_time in ["10-02-2018 13:29:00",
                  "10-02-2018 13:30:00",
                  "10-02-2018 13:35:00",
                  "11-02-2018 13:29:00",
                  "11-02-2018 13:30:00",
                  "11-02-2018 13:38:00",
                  "9-02-2018 13:30:00"]:
    debug("UPDATE NEEDED: {0}".format(is_update_needed(get_timestamp(test_check_time))))
    debug('*'*80)

def get_last_update(c):
  last_update = c.execute("SELECT MAX(timestamp) FROM ticks").fetchone()[0]
  if not last_update:
    last_update = 0

  return last_update

def update_system(systemName, local = False):
  data_system = get_json_data("system_{0}.json".format(systemName),
                   "https://www.edsm.net/api-v1/system",
                   {'systemName': systemName,'showPrimaryStar':1,'showInformation':1}, 
                   local)
  return data_system

def update_state_entry(timestamp,state_name,state_type,faction_name, system_name, trend):
  conn = get_db_connection()
  c = conn.cursor()
  values = [timestamp,state_name,state_type,faction_name, system_name, trend]
  c.execute("INSERT INTO faction_system_state VALUES",values)
  c.commit()

def update_tick(conn,cur_time = None, local = False, history = False,forced=False):
  current_time = get_timestamp(cur_time)
  c = conn.cursor()
  if not forced:
    if not is_update_needed(conn,current_time) and not history:
      debug("UPDATE NOT NEEDED")
      return False
    else:
      debug("UPDATE NEEDED")
  else:
    debug("UPDATE FORCED")
  if not history:
    print("update TICK")
    c.execute("INSERT INTO ticks VALUES (?)",[current_time])
  star_systems = fetch_systems("population > 0 ORDER BY population")
  total_systems = len(star_systems)
  current_start_system = 1
  for star_system in star_systems:
    systemName = star_system[0]
    system_info = update_system(systemName)
    sys.stdout.write("Updating System {0} [{1}/{2}]           \r".format(systemName,current_start_system,total_systems))
    current_start_system += 1
    sys.stdout.flush()
    values = [current_time,systemName,system_info['information']['faction'],system_info['information']['security']]
    if not history:
      c.execute("INSERT INTO system_status VALUES (?,?,?,?)",values)
    
    data_factions = get_json_data("factions_{0}.json".format(systemName),
                         "https://www.edsm.net/api-system-v1/factions",
                         {'systemName': systemName,'showHistory':1}, 
                         local)
    if not data_factions['factions']:
      return False
    
    for faction in data_factions['factions']:
      system_faction_entries = []
      active_state_entries = []
      pending_state_entries = []
      recovering_state_entries = []  
      if history:
        for timestamp in faction['stateHistory']:
          state = faction['stateHistory'][timestamp]
          active_state_entries.append([int(timestamp),state,'activeState',faction['name'],systemName,0])
          #print(timestamp,state)
        for timestamp in faction['influenceHistory']:
          system_faction_entries.append([int(timestamp),
            faction['name'],
            systemName,
            faction['influenceHistory'][timestamp]])
        if faction['recoveringStatesHistory']:
          for timestamp,state in faction['recoveringStatesHistory'].items():
            if not state:
              continue
            state = state[0]
            recovering_state_entries.append([int(timestamp),
                                  state['state'],
                                  "recoveringState",
                                  faction['name'],
                                  systemName,
                                  state['trend']])
        if faction['pendingStatesHistory']:
          for timestamp,state in faction['pendingStatesHistory'].items():
            if not state:
              continue
            state = state[0]
            pending_state_entries.append([int(timestamp),
                                  state['state'],
                                  "pendingState",
                                  faction['name'],
                                  systemName,
                                  state['trend']])
      else: 
        system_faction_entries.append([current_time,
                                        faction['name'],
                                        systemName,
                                        faction['influence']])
        active_state_entries.append([current_time,faction['state'],'activeState',faction['name'],systemName,0])
        for state in faction['recoveringStates']:
          pending_state_entries.append([current_time,
                                state['state'],
                                "recoveringState",
                                faction['name'],
                                systemName,
                                state['trend']])
        for state in faction['pendingStates']:
          recovering_state_entries.append([current_time,
                                state['state'],
                                "pendingState",
                                faction['name'],
                                systemName,
                                state['trend']])
      for values in system_faction_entries:
        if history:
          check_query = """
          SELECT * FROM faction_system WHERE
          date={0} AND
          name="{1}" AND
          system="{2}" AND
          influence={3}""".format(*values)
          c.execute(check_query)
          if c.fetchone():
            #debug("ENTRY_ALREADY_EXISTS")
            continue
        c.execute("INSERT INTO faction_system VALUES (?,?,?,?)",values)
        
      for values in active_state_entries:
        c.execute("INSERT INTO faction_system_state VALUES (?,?,?,?,?,?)",values)
      for values in pending_state_entries:
        c.execute("INSERT INTO faction_system_state VALUES (?,?,?,?,?,?)",values)
      for values in recovering_state_entries:
        c.execute("INSERT INTO faction_system_state VALUES (?,?,?,?,?,?)",values)
        
        if history:  
          conn.commit()
  conn.commit()
  return True

def get_system_status(systemName,timestamp  = None):
  conn = get_db_connection()
  if not timestamp:
    timestamp = get_last_update()
  else:
    timestamp = get_timestamp(timestamp)
  c = conn.cursor()
  c.execute("""SELECT DISTINCT faction_system.date,
                        faction_system.system,
                        faction_system.name,
                        faction_system.influence,
                        faction_system.state,
                        faction_system_state.state_name,
                        faction_system_state.state_type
                  FROM faction_system, faction_system_state
                  WHERE faction_system.system = '{0}'
                  AND faction_system_state.system_name = '{0}'
                  AND faction_system.date = {1}
                  AND faction_system_state.date = {1}""".format(systemName,timestamp))
  return [systemName,c.fetchall()]

def get_system_status_timespan(systemName, initialTimestamp,endTimestamp = None):
  conn = get_db_connection()
  if not endTimestamp:
    endTimestamp = get_time()
  c = conn.cursor()
  query = '''SELECT DISTINCT faction_system.date,
                        faction_system.system,
                        faction_system.name,
                        faction_system.influence,
                        faction_system.state,
                        faction_system.controller,
                        faction_system_state.state_name,
                        faction_system_state.state_type,
                        faction_system_state.trend
                  FROM faction_system, faction_system_state
                  WHERE faction_system.system = "{0}"
                  AND faction_system_state.system_name = "{0}"'''.format(systemName)
  c.execute(query)  
  all_entries = c.fetchall()
  return [systemName,[ entry for entry in all_entries if entry[0] >= initialTimestamp and entry[0] < endTimestamp]]

def get_all_entries():
  conn = get_db_connection()
  c = conn.cursor()
  c.execute("SELECT * FROM faction_system")  
  return c.fetchall()


class Faction:
  def __init__(self,conn,faction_name):
    c = conn.cursor()
    self.name = faction_name
    self.ok = False
    self.json = ""
    c.execute('SELECT allegiance,government,is_player,native_system FROM Factions WHERE faction_name = "{0}"'.format(faction_name))
    try:
      self.allegiance, self.government, self.is_player, self.native_system = c.fetchone()
      self.ok = True
    except:
      self.ok = False
    if self.ok:
      self.json = {"name":self.name,"allegiance":self.allegiance,"government":self.government,"isPlayer":self.is_player,"native_system":self.native_system}
    print(faction_name,"OK:",self.ok)
  def __repr__(self):
    return str(self.json)

  @classmethod
  def get_all_factions(cls,criteria=None):
    criteria_sql = ""
    if criteria:
      if isinstance(criteria, (list,tuple)):
        criteria_sql = " WHERE " + " AND ".join(criteria)
      elif isinstance(criteria,str):
        criteria_sql = " WHERE " + criteria
      else:
        return None
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT faction_name FROM Factions{0}'.format(criteria_sql))
    factions = c.fetchall()
    factions = [Faction(faction[0]) for faction in factions]
    return factions
  
  def get_retreat_risk(self,threshold = RETREAT_THRESHOLD):
    systems = self.get_systems()
    risked = []
    if systems:
      for system_name in systems:
        influence = self.get_status_in_system(system_name).popitem()[1]['status']['influence']
        if influence > 0.0 and influence < threshold:
          risked.append([system_name,influence])
    return(risked)
  
  def get_expansion_risk(self,threshold = EXPANSION_THRESHOLD):
    systems = self.get_systems()
    risked = []
    if systems:
      for system_name in systems:     
        influence = self.get_status_in_system(system_name).popitem()[1]['status']['influence']
        if influence > threshold:
          risked.append([system_name,influence])
      return(risked)
  
  def get_expansion_risk_system(self,system,threshold = EXPANSION_THRESHOLD):
    systems = self.get_systems()
    risked = []
    if systems:
      for system_name in systems:     
        influence = self.get_status_in_system(system_name).popitem()[1]['status']['influence']
        if influence > threshold:
          risked.append([system_name,influence])
      return(risked)
  
  def get_systems(self, start_timestamp = None, end_timestamp = None):
    if not self.ok:
        return None  
    conn = get_db_connection()
    c = conn.cursor()
    if start_timestamp == None:
      start_timestamp = get_last_update()
    else:
      start_timestamp = get_time(start_timestamp)
    if end_timestamp == None:
      end_timestamp = get_last_update()
      
    else:
      end_timestamp = get_time(end_timestamp)
    c.execute('SELECT DISTINCT system FROM faction_system WHERE name = "{0}" AND date >= {1} AND date <= {2}'.format(self.name,start_timestamp,end_timestamp))
    systems = [system[0] for system in c.fetchall() ]
    return(systems)
  
  def get_current_influence_in_system(self,conn, system_requested):
    if not self.ok:
      return None
    if isinstance(system_requested,System):
      system_requested = system_requested.name
    c = conn.cursor()
    c.execute('SELECT influence FROM faction_system WHERE system = "{0}" AND name = "{1}" and date = {2}'.format(system_requested,self.name,get_last_update(c)))  
    influence_data = c.fetchone()
    if len(influence_data) > 0: 
      return influence_data[0]
    return None
  
  def get_current_pending_states(self):
    if not self.ok:
        return None
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT DISTINCT state_name, trend FROM faction_system_state WHERE faction_name = "{0}" AND date ={1} AND state_type="pendingState"'.format(self.name,get_last_update()))
    return c.fetchall()
  
  def get_current_recovering_states(self):
    if not self.ok:
        return None
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT DISTINCT state_name, trend FROM faction_system_state WHERE faction_name = "{0}" AND date ={1} AND state_type="recoveringState"'.format(self.name,get_last_update()))
    return c.fetchall()
  
  def get_state(self, conn, start_timestamp = None, end_timestamp = None):
    c= conn.cursor()
    if start_timestamp == None:
      start_timestamp = get_last_update(c)
    else:
      start_timestamp = get_time(start_timestamp)
    if end_timestamp == None:
      end_timestamp = get_last_update(c)
    state = c.execute('SELECT state_name FROM faction_system_state WHERE faction_name ="{0}"  AND date >= {1} AND date <= {2}'.format(self.name,start_timestamp,end_timestamp)).fetchone()["state_name"]
    return state
  
  def get_status_in_system(self,system_name, start_timestamp = None, end_timestamp = None):
    if not self.ok:
        return None
    conn = get_db_connection()
    c = conn.cursor()
    if start_timestamp == None:
      start_timestamp = get_last_update()
    else:
      start_timestamp = get_time(start_timestamp)
    if end_timestamp == None:
      end_timestamp = get_last_update()
    else:
      end_timestamp = get_time(end_timestamp)

    timestamps = defaultdict(dict)
    c.execute('SELECT date,influence FROM faction_system WHERE name = "{0}" AND system = "{1}" AND date >= {2} AND date <= {3}'.format(self.name,system_name,start_timestamp,end_timestamp))
    status_entries =  list(c.fetchall())
    c.execute('SELECT date,state_name,state_type,trend FROM faction_system_state WHERE faction_name = "{0}" AND system_name = "{1}" AND date >= {2} AND date <= {3}'.format(self.name,system_name,start_timestamp,end_timestamp))
    state_entries = list(c.fetchall())
    for entry in state_entries:
      timestamp,state_name,state_type,trend = entry
      timestamp = str(int(float(timestamp)))
      timestamps[timestamp][state_type + 's'] = {'state':state_name, 'trend':trend}
    for entry in status_entries:
      timestamp,influence = entry
      timestamp = str(int(float(timestamp)))
      timestamps[timestamp]['status'] = {'influence':influence,'state':state_name}
    return timestamps

class System:
  def __init__(self,c,system_name):
    self.name = system_name
    self.ok = False
    self.json = ""
#    try:
    result = c.execute('SELECT population,economy,distance,x,y,z FROM Systems WHERE name = "{0}"'.format(system_name)).fetchone()
    self.population, self.economy, self.distance, self.x, self.y, self.z = result
    self.ok = True
#    except:
#      print("ERROR getting data!!!")
    if self.ok:
      self.json =  {"name":self.name,"population":self.population,"economy":self.economy,"distance":self.distance}
  
  @classmethod
  def get_all_systems(cls,conn):
    c = conn.cursor()
    c.execute('SELECT name FROM Systems')
    factions = [System(conn,faction[0]) for faction in c.fetchall()]
    return factions
  
  def get_closest_systems(self,conn,limit = None):
    if not self.ok:
      return None
    c = conn.cursor()
    all_systems = System.get_all_systems(conn)
    system_list = []
    for near_system in all_systems:
      system_list.append({"system":near_system.name,"distance":distance([near_system.x,near_system.y,near_system.z],[self.x,self.y,self.z])})
    return sorted(system_list,key=lambda x:[x["distance"]])[1:limit]
  
  def get_next_expansion_system(self,conn):
    for candidate in self.get_closest_systems(conn):
      candidate_system = System(conn,candidate["system"])
      if len(candidate_system.get_factions(conn)) <= EXPANSION_FACTION_THRESHOLD:
        return({"system":candidate["system"],"distance":candidate["distance"]})
      else:
        print(candidate,"- NO:",len(candidate_system.get_factions(conn)),"factions")
  
  def get_controller_and_state(self,c,timestamp = None):
    if not self.ok:
      return None
    if not timestamp:
      timestamp = get_last_update(c)
    faction_name = c.execute('SELECT controller_faction FROM system_status WHERE system = "{0}" AND date = "{1}"'.format(self.name,timestamp)).fetchone()["controller_faction"]
    state = c.execute('SELECT state_name FROM faction_system_state WHERE system_name = "{0}" AND faction_name ="{1}" AND date = "{2}"'.format(self.name,faction_name,timestamp)).fetchone()["state_name"]
    return {"name":faction_name,"state":state}
    
  def get_war_risk(self,threshold = WAR_THRESHOLD):
    factions = self.get_factions()
    factions_in_risk = []
    if factions:
      for faction1,faction2 in itertools.combinations(factions,2):
        influence1 = faction1.get_current_influence_in_system(self.name)
        influence2 = faction2.get_current_influence_in_system(self.name)
        if influence1 and influence2:
          if abs(influence1 - influence2) < threshold:
            factions_in_risk.append([faction1,faction2])
    return factions_in_risk
      
  def get_factions(self, conn, start_timestamp = None, end_timestamp = None):
    if not self.ok:
      return None
    c = conn.cursor()
    if start_timestamp == None:
      start_timestamp = get_last_update(c)
    else:
      start_timestamp = get_time(start_timestamp)
    if end_timestamp == None:
      end_timestamp = get_last_update(c)
    else:
      end_timestamp = get_time(end_timestamp)
    c.execute('SELECT name FROM faction_system WHERE system = "{0}" AND date >= {1} AND date <= {2} AND influence > 0.0'.format(self.name,start_timestamp,end_timestamp))
    factions = [tuple(faction)[0] for faction in c.fetchall()]
    return factions
  
  def get_current_factions(self,conn, start_timestamp = None, end_timestamp = None):
    return self.get_factions(conn,start_timestamp,end_timestamp)
    
  def __repr__(self):
    return str(self.json)

def get_factions_with_retreat_risk(threshold = RETREAT_THRESHOLD):
  ret_risked = []
  for faction in Faction.get_all_factions():
    risked = faction.get_retreat_risk(threshold)
    if risked:
      for system in risked:
        system_name, influence = system
        if not faction.name.startswith(system_name):
          ret_risked.append({"faction":faction.name,"system":system_name,"influence":influence, "state":faction.state})
  return ret_risked

def get_factions_with_expansion_risk(threshold = EXPANSION_THRESHOLD):
  ret_risked = []
  for faction in Faction.get_all_factions():
    risked = faction.get_expansion_risk(threshold)
    if risked:
      for system in risked:
        system_name, influence = system
        if not faction.name.startswith(system_name):
          ret_risked.append({"faction":faction.name,"system":system_name,"influence":influence, "state":faction.state})
  return ret_risked

def get_trend_text(trend):
  if trend == 0:
    return "="
  elif trend > 0:
    return "+"
  else:
    return "-"

def get_retreat_risk_report(threshold = RETREAT_THRESHOLD):
  report = "\n" + "*"*10 + "RETREAT RISK REPORT" + "*"*10 + "\n\n"
  
  report += "The following factions are in risk of enter in state of Retreat:\n"
  for risk in get_factions_with_retreat_risk(threshold):
    pending_states = ", ".join(["{0} ({1})".format(pending_state,get_trend_text(trend)) for pending_state, trend in Faction(risk['faction']).get_current_pending_states()])
    if not pending_states:
      pending_states = "None"
    recovering_states = ", ".join(["{0} ({1})".format(recovering_state,get_trend_text(trend)) for recovering_state, trend in Faction(risk['faction']).get_current_recovering_states()])
    if not recovering_states:
      recovering_states = "None"
  
    report += "'{0}' in system '{1}' (Influence: {2:.3g} %, State: {3}, Pending: {4}, Recovering: {5}, Distance: {6} lys)\n".format(risk['faction'],risk['system'],risk['influence']*100.0,risk['state'], pending_states, recovering_states,System(risk['system']).distance)
  return report

def get_war_risk_report(threshold = WAR_THRESHOLD):
  report = "\n" + "*"*10 + "WAR RISK REPORT" + "*"*10 + "\n"
  report += "The following factions are in risk of enter in state of War:\n"
  for system in System.get_all_systems():
    for faction1, faction2 in system.get_war_risk(threshold):
      report += "'{0}' ({1:.2f}%) versus '{2}' ({3:.2f}%) in '{4}'\n".format(faction1.name, faction1.get_current_influence_in_system(system.name)*100.0,
                                                                  faction2.name,faction2.get_current_influence_in_system(system.name)*100.0,system.name)
  return report

def get_expansion_risk_report(threshold = EXPANSION_THRESHOLD):
  report = "\n" + "*"*10 + "EXPANSION RISK REPORT" + "*"*10 + "\n"
  report += "The following factions are in risk of enter in state of Expansion:\n"
  for risk in get_factions_with_expansion_risk(threshold):
    report += "'{0}' from system '{1}' (Influence: {2:.3g} %, State: {3}, Distance: {4} lys)\n".format(risk['faction'],risk['system'],risk['influence']*100.0,risk['state'], System(risk['system']).distance)
  return report


systems_controlled = ["Naunin"]
def fresh_hard_update(local = False):
  conn = sqlite3.connect(DATABASE)
  clean_fixed_tables()
  clean_updates()
  for controlled_system in systems_controlled:
    fill_systems_in_bubble(controlled_system, EXPANSION_RADIUS, local)
  update_tick(conn,history=False)
  conn.close()
  
if 0:
  conn = sqlite3.connect(DATABASE)
  
  fresh_start = False
  
  systemName = "Naunin"
  if fresh_start:
    clean_fixed_tables()
    clean_updates()
  #clean_local_json_path()
    fill_systems_in_bubble(systemName,EXPANSION_RADIUS,local=True)
    update_tick(get_timestamp("23-02-2018 13:30:00"),local = True,history = True)
  update_tick()
  
  if 0:
    defence = Faction("Defence Party of Naunin")
    print(defence)  
    
    for faction in Faction.get_all_factions(('faction_name LIKE "%Naunin%"')):
      print(faction)
    
  
  
    print(System.get_all_systems())
    
    my_system = System("Maopi")
    f = Faction('Naunin Jet Netcoms Incorporated')
    
    kb = Faction("Kupol Bumba Alliance")
    print(kb)
    print(kb.get_current_influence_in_system("Naunin"))
    
   
  if 1:
    f = Faction('Movement for Ngalu Democrats')
    print("PENDING STATES:",f.get_current_pending_states())
    print("RECOVERING STATES:",f.get_current_recovering_states())
    current_system = System(systemName)
    factions = current_system.get_factions()

    print(get_retreat_risk_report(0.025))
    print(get_war_risk_report(0.01))
    print(get_expansion_risk_report(0.65))

  systemName = "Naunin"
  for faction in System(systemName).get_factions():
    print(faction.name)
    status_history = faction.get_status_in_system(systemName,start_timestamp=0)
    if status_history:
      for entry in sorted(status_history):
        print(get_utc_time_from_epoch(entry),status_history[entry])
 
conn = sqlite3.connect(DATABASE)
s = System(conn, "Naunin")
print(s.get_closest_systems(conn,5))
print(s.get_next_expansion_system(conn))

conn.close()
 