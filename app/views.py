from flask import (Flask, render_template, request, redirect,
                   jsonify, url_for, flash, make_response)
from flask import session as login_session
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from models import (Base, Rating, Company, Manufacturer, Publisher,
                    Developer, System, User, Role, UserRole, Game,
                    GamePlatform)
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
import requests
import random
import string


app = Flask(__name__)


# Connect to Database and create database session
engine = create_engine('sqlite:///data/games.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

@app.route('/')
def homePage():
    developer = session.query(Company).filter_by(id=1).first()
    return render_template('home.html', developer=developer)


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=5000)