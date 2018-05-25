from urllib.request import urlopen
from bs4 import BeautifulSoup
import re
from distutils.filelist import findall
import datetime
from dateutil.relativedelta import relativedelta


YEAR_DIFFERENCE = 1286

galnet_page = 'https://community.elitedangerous.com/en/galnet'
page = urlopen(galnet_page)
soup = BeautifulSoup(page, 'html.parser')
articles = soup.find_all('div', attrs={'class': 'article'})


def get_date(article):
  return article.find('div', attrs={'class': 'i_right'}).text

def get_title(article):
  return article.find('h3', attrs={'class': 'hiLite galnetNewsArticleTitle'}).text


re_status_port = ".*?, .*"
date_str = "%d %b %Y"


def get_startport_status():
  starport_status = None
  for article in list(articles):
 
    article_title = get_title(article)
    if article_title.strip() == "Starport Status Update":
      starport_status = article
      break
  if starport_status:
    article_date = get_date(starport_status)
    epochdate = datetime.datetime.strptime(article_date,date_str).date()
    epochdate -= relativedelta(years=YEAR_DIFFERENCE)
    print(datetime.datetime.strftime(epochdate,"%d %b %Y"))
    stations = re.findall(re_status_port,starport_status.text )
    for station in [station.split(',') for station in stations if station.strip()]:
      station_name,station_system = station[0],station[1].strip()
      print("The station '{0} in the '{1}' system has been affected by UA Bombing".format(station_name,station_system))
      
get_startport_status()