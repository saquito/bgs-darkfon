from . import bgs
import json
from . import db

# from flask import (
#     Blueprint, flash, g, redirect, render_template, request, session, url_for
# )

from flask import (
    Blueprint, render_template, request,send_from_directory
)

bp = Blueprint('query', __name__, url_prefix='/query')
bp_media = Blueprint('media', __name__, url_prefix='/media')

@bp.route('/', methods=('GET', 'POST'))
def get_main():
  return ("Hello, World")

@bp.route('/system/<system_name>', methods=('GET', 'POST'))
def get_system_view(system_name):
  system_name = system_name.replace("_"," ")
  response = render_template('query/system_view_start.html')
  response += "<h2>{0}</h2>".format(system_name) 
  response += """<label class="table-header">Factions</label>"""
  response += """<table><tr><th>Faction</th><th>State</th><th>Influence</th><th>Player</th><th>Last Update</th></tr></tr>"""
  factions = json.loads(get_system_factions_static(system_name))
  for faction in factions:
    response +="<tr>"
    response += "<td>{0}</td>".format(faction["name"])
    response += "<td>{0}</td>".format(faction["state"])
    response += "<td>{0}</td>".format(faction["influence"])
    response += "<td>{0}</td>".format("No" if faction["is_player"] else "Yes")
    response += "<td>{0}</td>".format(faction["last_update"])
    response +="</tr>"
  response +="</table>"

  response += """<table><label class="table-header">Nearest Systems</label><tr><th>System</th><th>Distance</th><th>Number of Factions</th><th>Has Player</th></tr>"""
  near_systems = json.loads(get_near_systems_static(system_name,controller_faction=bgs.FACTION_CONTROLLED))
  next_expansion = False
  
  for near_system in near_systems:
    expansion_formatting = ' style="background-color:#330000"'
    if near_system["controlled"]:
      expansion_formatting = ' style="background-color:#555555"'
    elif bgs.EXPANSION_FACTION_MAX > near_system["num_factions"]:
      if not next_expansion:
        next_expansion = True
        expansion_formatting = ' style="background-color:#003300"'
      else:
        expansion_formatting = ' style="background-color:#000033"'
    response +="<tr{0}>".format(expansion_formatting)
    response += "<td><a href='{1}'>{0}</td>".format(near_system["name"],near_system["name"].replace(" ","_"))
    response += "<td>{0:.2f}</td>".format(near_system["distance"])
    response += "<td>{0}</td>".format(near_system["num_factions"])
    response += "<td>{0}</td>".format("Yes" if near_system["has_player"] else "No")
    response +="</tr>"
  response +="</table>"
  response += render_template('query/influence_graph.html')
  response += render_template('query/system_view_end.html')
  return response

@bp.route('/system_controller', methods=('GET', 'POST'))
def get_system_controller():
  if request.method == 'POST':
    conn = db.get_db()
    s = bgs.System(conn,request.data.decode('utf-8'))
  return json.dumps([s.get_controller_and_state(conn)])

@bp.route('/faction_state', methods=('GET', 'POST'))
def get_faction_state():
  if request.method == 'POST':
    conn = db.get_db()
    f = bgs.Faction(conn,request.data.decode('utf-8'))
    factions = [{"state":state} for state in f.get_current_factions(conn)]
  return json.dumps(factions)

@bp.route('/system_factions', methods=('GET', 'POST'))
def get_system_factions():
  if request.method == 'POST':
    system_name = request.data.decode('utf-8')
    system_name = system_name.replace("_"," ")
    return get_system_factions_static(system_name)
  return ""

def get_system_factions_static(system_name):
  result = []
  conn = db.get_db()
  star_system = bgs.System(conn,system_name)
  if star_system:
    system_factions = star_system.get_current_factions(conn)
    for faction in system_factions:
      f = bgs.Faction(conn,faction)
      if f:
        tick,state_type,state = f.get_state(conn)
        is_player = True
        if f.is_player:
          is_player = False
        influence = f.get_current_influence_in_system(conn,star_system)
        print("INFLUENCE:",influence)
        if tick:
          tick = bgs.get_utc_time_from_epoch(tick)
        if state and influence:
          faction_dict = {"name":faction,"is_player": is_player,"last_update":tick,"state":state,"influence":"{0:.2f}".format(influence*100.0)}
          result.append(faction_dict)
  if result:
    print("RESULT",result)
    result = sorted(result,key=lambda x: float(x["influence"]),reverse=True)
  return json.dumps(result)

@bp.route('/near_systems', methods=('GET', 'POST'))
def get_near_systems():
  if request.method == 'POST':
    system_name = request.data.decode('utf-8')
    return get_near_systems_static(system_name,controller_faction=bgs.FACTION_CONTROLLED)
  return ""

def get_near_systems_static(system_name,controller_faction=None):
  result = []
  conn = db.get_db()
  star_system = bgs.System(conn,system_name)
  if star_system:
    near_systems = star_system.get_closest_systems(conn, 10)
    for near_sys in near_systems:
      factions = bgs.System(conn,near_sys["system"]).get_factions(conn)
      num_factions = len(factions)
      has_player_faction = False
      controlled = False
      for faction in factions:
        faction_obj = bgs.Faction(conn,faction)
        if faction_obj.name == controller_faction:
          controlled = True
        if faction_obj.is_player:
          has_player_faction = True
      result.append({"name":near_sys["system"],"distance":near_sys["distance"],"num_factions":num_factions,"controlled":controlled,"has_player":has_player_faction})
  if result:
    result = sorted(result,key=lambda x: float(x["distance"]))
    print(result)
  return json.dumps(result)

@bp.route('/next_expansion', methods=('GET', 'POST'))
def get_next_expansion():
  result = []
  if request.method == 'POST':
    conn = db.get_db()
    star_system = bgs.System(conn,request.data.decode('utf-8'))
    if star_system:
        next_expansion = star_system.get_next_expansion_system(conn)["system"]
        print(next_expansion)
        result = next_expansion
  return next_expansion

@bp.route('/main_test', methods=('GET', 'POST'))
def main_test():
  return render_template('query/main_test.html')

@bp.route('/system/<system_name>', methods=('GET', 'POST'))
def main_test2(system_name):
  return render_template('query/main_test.html')

@bp.route('/near_systems_list', methods=('GET', 'POST'))
def get_near_systems_list():
  return render_template('query/near_systems_list.html')


@bp.route('/faction_system_list', methods=('GET', 'POST'))
def get_faction_system_list():
  return render_template('query/faction_system_list.html')

@bp.route('/system_info', methods=('GET', 'POST'))
def get_system_info_pane():
  return render_template('query/system_info.html')

@bp.route('/system_info_test', methods=('GET', 'POST'))
def get_system_info_test_pane():
  return render_template('query/system_info_test.html')

@bp_media.route('/media/<path:filename>')
def download_file(filename):
  return send_from_directory("media", filename, as_attachment=True)
