# -*- coding: utf-8 -*-
"""
This file will grab a snapshot from a network camera.
"""

import argparse
import sys
import logging
import re
import pytz
import netrc
import requests
from requests.auth import HTTPDigestAuth
import sqlalchemy as db
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, Float, String, Date, DateTime
from axis_snapshot import __version__
from datetime import date
from datetime import datetime
from tzwhere import tzwhere
from pathlib import Path

__author__ = "Tom Pusateri"
__copyright__ = "Tom Pusateri"
__license__ = "mit"

_logger = logging.getLogger(__name__)

Base = declarative_base()

class Sunrise(Base):
    __tablename__ = 'sunrises'

    id = Column('id', Integer, primary_key=True)
    name = Column(String)
    date = Column(Date)
    lat = Column(Float)
    lng = Column(Float)
    sunrise_time = Column(DateTime)
    sunset_time = Column(DateTime)

    def __repr__(self):
        return 'Sunrise %d: %s, %s' % (self.id, self.name, self.sunrise_time)

def parse_args(args):
    """Parse command line parameters

    Args:
      args ([str]): command line parameters as list of strings

    Returns:
      :obj:`argparse.Namespace`: command line parameters namespace
    """
    parser = argparse.ArgumentParser(
        description="Take a snapshot from a network camera")
    parser.add_argument(
        "--version",
        action="version",
        version="axis_snapshot {ver}".format(ver=__version__))
    parser.add_argument(
        "-n",
        "--name",
        dest="name",
        help="location name",
        metavar="NAME")
    parser.add_argument(
        "-f",
        "--force",
        help="Force image request if not between sunrise/sunset",
        action='store_true')
    parser.add_argument(
        "-l",
        "--latitude",
        dest="latitude",
        help="latitude",
        metavar="FLOAT")     # 35.800783
    parser.add_argument(
        "-g",
        "--longitude",
        dest="longitude",
        help="longitude",
        metavar="FLOAT")    # -78.645814
    parser.add_argument(
        "-v",
        "--verbose",
        dest="loglevel",
        help="set loglevel to INFO",
        action="store_const",
        const=logging.INFO)
    parser.add_argument(
        dest="url",
        help="camera URL",
        metavar="URL")
    return parser.parse_args(args)


def setup_logging(loglevel):
    """Setup basic logging

    Args:
      loglevel (int): minimum loglevel for emitting messages
    """
    logformat = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    logging.basicConfig(level=loglevel, stream=sys.stdout,
                        format=logformat, datefmt="%Y-%m-%d %H:%M:%S")

def get_sunrise(lat, lng):
    payload = {'lat': lat, 'lng': lng, 'formatted': '0', 'date': 'today'}
    r = requests.get('https://api.sunrise-sunset.org/json', params=payload)
    if r.status_code != requests.codes.ok:
        _logger.debug("Sunrise API returned error: {}", r.status_code)
    if r.headers.get('content-type') != 'application/json':
        _logger.debug("expected JSON response from Sunrise API")
    try:
        json = r.json()
    except ValueError:
        _logger.debug("invalid JSON from Sunrise API")
    return json

def sql_session(dir):
    engine = db.create_engine('sqlite:///' + dir + '/sunrise.sqlite', echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        engine.connect()
    except db.exc.DBAPIError:
        Base.metadata.create_all(engine)
    metadata = db.MetaData()

    try:
        db.Table('sunrises', metadata, autoload=True,
                 sqlite_autoincrement=True, autoload_with=engine)
    except db.exc.NoSuchTableError:
        Base.metadata.create_all(engine)
    return session

def add_sunrise(session, name, lat, lng):
    json = get_sunrise(lat, lng)
    sunrise = datetime.fromisoformat(json['results']['sunrise'])
    sunset = datetime.fromisoformat(json['results']['sunset'])
    today = Sunrise(name=name, date=date.today(), lat=lat, lng=lng,
                    sunrise_time=sunrise,
                    sunset_time=sunset)
    session.add(today)
    session.commit()
    return today

def password_from_netrc(remote_url):
   rec = re.compile(r"https?://(www\.)?")
   url_no_proto = rec.sub('',remote_url).strip().strip('/')
   try:
       auth = netrc.netrc().authenticators(url_no_proto)
   except IOError:
       print('~/.netrc does not exist.')
       quit(1)
   if auth is None:
       print('%s not found in ~/.netrc' % url_no_proto)
       print('example: machine %s login <Username> password <Password>' % url_no_proto)
       quit(1)
   username = (auth[0])
   password = auth[2]
   return username, password

def main(args):
    """Main entry point allowing external calls

    Args:
      args ([str]): command line parameter list
    """
    args = parse_args(args)
    setup_logging(args.loglevel)

    dir = 'snapshots/' + args.name
    Path(dir).mkdir(parents=True, exist_ok=True)

    session = sql_session(dir)
    today = session.query(Sunrise).filter_by(date=date.today()).first()
    if today is None:
        today = add_sunrise(session, args.name, args.latitude, args.longitude)
    now = datetime.utcnow()
    username, password = password_from_netrc(args.url)

    if args.force == True or (now > today.sunrise_time and now < today.sunset_time):
        where = tzwhere.tzwhere()
        timezone_str = where.tzNameAt(float(args.latitude), float(args.longitude))
        local_timezone = pytz.timezone(timezone_str)
        utcnow = now.replace(tzinfo=pytz.utc)
        local_now = utcnow.astimezone(local_timezone)
        path = local_now.strftime('%Y%m%d-%H%M%S%z') + '_' + args.name + '.jpg'

        r = requests.get(args.url, auth=HTTPDigestAuth(username, password), verify=False, stream=True)
        if r.status_code == requests.codes.ok:
            with open(dir + '/' + path, 'wb') as f:
                for chunk in r.iter_content(4096):
                    f.write(chunk)


def run():
    """Entry point for console_scripts
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
