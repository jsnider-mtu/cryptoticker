#!/usr/bin/env python3
import logging
import json
import os
import socket
import sys
import textwrap
import time
import urllib

import currency
import requests
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import yaml
from guizero import (
    App,
    Combo,
    Picture,
    PushButton,
    Text,
)
from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageOps,
)

dirname = os.path.dirname(__file__)
picdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'images')
fontdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'fonts/googlefonts')
configfile = os.path.join(os.path.dirname(os.path.realpath(__file__)),'config.yaml')
font_date = ImageFont.truetype(os.path.join(fontdir,'PixelSplitter-Bold.ttf'),11)
headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

def _place_text(img, text, x_offset=0, y_offset=0,fontsize=40,fontstring="Forum-Regular", fill=0):
  '''
  Put some centered text at a location on the image.
  '''
  draw = ImageDraw.Draw(img)
  try:
    filename = os.path.join(dirname, './fonts/googlefonts/'+fontstring+'.ttf')
    font = ImageFont.truetype(filename, fontsize)
  except OSError:
    font = ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans.ttf', fontsize)
  img_width, img_height = img.size
  text_width, _ = font.getsize(text)
  text_height = fontsize
  draw_x = (img_width - text_width)//2 + x_offset
  draw_y = (img_height - text_height)//2 + y_offset
  draw.text((draw_x, draw_y), text, font=font,fill=fill )

def beanaproblem(message):
  # A visual cue that the wheels have fallen off
  thebean = Image.open(os.path.join(picdir,'thebean.bmp'))
  image = Image.new('L', (264, 176), 255)    # 255: clear the image with white
  draw = ImageDraw.Draw(image)
  image.paste(thebean, (60,45))
  draw.text((95,15),str(time.strftime("%-H:%M %p, %-d %b %Y")),font=font_date,fill=0)
  writewrappedlines(image, "Issue: "+message)
  return image

def currencystringtolist(currstring):
  # Takes the string for currencies in the config.yaml file and turns it into a list
  curr_list = currstring.split(",")
  curr_list = [x.strip(' ') for x in curr_list]
  return curr_list

def display_image(img):
  global app
  global center_image
  center_image.destroy()
  center_image = Picture(app, image=img, grid=[0,1,2,1])

def fullupdate(config,lastcoinfetch):
  """  
  The steps required for a full update of the display
  """
  global crypto_choice
  global fiat_choice
  other={}
  try:
    pricestack, ATH = getData(config, other, crypto_choice.value, fiat_choice.value)
    # generate sparkline
    makeSpark(pricestack)
    # update display
    image=updateDisplay(config, pricestack, other, crypto_choice.value, fiat_choice.value)
    display_image(image)
    lastgrab=time.time()
    time.sleep(0.2)
  except Exception as e:
    message="Data pull/print problem"
    image=beanaproblem(str(e)+" Line: "+str(e.__traceback__.tb_lineno))
    display_image(image)
    time.sleep(20)
    lastgrab=lastcoinfetch
  return lastgrab

def getData(config,other,crypto,fiat):
    """
    The function to grab the data (TO DO: need to test properly)
    """
    sleep_time = 10
    num_retries = 5
    whichcoin = crypto
    logging.info("Getting Data")
    days_ago=int(config['ticker']['sparklinedays'])   
    endtime = int(time.time())
    starttime = endtime - 60*60*24*days_ago
    starttimeseconds = starttime
    endtimeseconds = endtime 
    geckourlhistorical = "https://api.coingecko.com/api/v3/coins/"+whichcoin+"/market_chart/range?vs_currency="+fiat+"&from="+str(starttimeseconds)+"&to="+str(endtimeseconds)
    logging.info(geckourlhistorical)
    for x in range(0, num_retries):   
        rawtimeseries, connectfail=  getgecko(geckourlhistorical)
        if connectfail== True:
            pass
        else:
            logging.info("Got price for the last "+str(days_ago)+" days from CoinGecko")
            timeseriesarray = rawtimeseries['prices']
            timeseriesstack = []
            length=len (timeseriesarray)
            i=0
            while i < length:
                timeseriesstack.append(float (timeseriesarray[i][1]))
                i+=1
            # A little pause before hiting the api again
            time.sleep(1)          
            # Get the price 
        if config['ticker']['exchange']=='default':
            geckourl = "https://api.coingecko.com/api/v3/coins/markets?vs_currency="+fiat+"&ids="+whichcoin
            logging.info(geckourl)
            rawlivecoin , connectfail = getgecko(geckourl)
            if connectfail==True:
                pass
            else:
                logging.info(rawlivecoin[0])   
                liveprice = rawlivecoin[0]
                pricenow= float(liveprice['current_price'])
                alltimehigh = float(liveprice['ath'])
                # Quick workaround for error being thrown for obscure coins. TO DO: Examine further
                try:
                    other['market_cap_rank'] = int(liveprice['market_cap_rank'])
                except:
                    config['display']['showrank']=False
                    other['market_cap_rank'] = 0
                other['volume'] = float(liveprice['total_volume'])
                timeseriesstack.append(pricenow)
                if pricenow>alltimehigh:
                    other['ATH']=True
                else:
                    other['ATH']=False
        else:
            geckourl= "https://api.coingecko.com/api/v3/exchanges/"+config['ticker']['exchange']+"/tickers?coin_ids="+whichcoin+"&include_exchange_logo=false"
            logging.info(geckourl)
            rawlivecoin, connectfail = getgecko(geckourl)
            if connectfail==True:
                pass
            else:
                theindex=-1
                upperfiat=fiat.upper()
                for i in range (len(rawlivecoin['tickers'])):
                    target=rawlivecoin['tickers'][i]['target']
                    if target==upperfiat:
                        theindex=i
                        logging.info("Found "+upperfiat+" at index " + str(i))
        #       if UPPERFIAT is not listed as a target theindex==-1 and it is time to go to sleep
                if  theindex==-1:
                    logging.info("The exchange is not listing in "+upperfiat+". Misconfigured - shutting down script")
                    sys.exit()
                liveprice= rawlivecoin['tickers'][theindex]
                pricenow= float(liveprice['last'])
                other['market_cap_rank'] = 0 # For non-default the Rank does not show in the API, so leave blank
                other['volume'] = float(liveprice['converted_volume']['usd'])
                alltimehigh = 1000000.0   # For non-default the ATH does not show in the API, so show it when price reaches *pinky in mouth* ONE MILLION DOLLARS
                logging.info("Got Live Data From CoinGecko")
                timeseriesstack.append(pricenow)
                if pricenow>alltimehigh:
                    other['ATH']=True
                else:
                    other['ATH']=False
        if connectfail==True:
            message="Trying again in ", sleep_time, " seconds"
            logging.info(message)
            time.sleep(sleep_time)  # wait before trying to fetch the data again
            sleep_time *= 2  # exponential backoff
        else:
            break
    return timeseriesstack, other

def getgecko(url):
  try:
    geckojson=requests.get(url, headers=headers).json()
    connectfail=False
  except requests.exceptions.RequestException as e:
    logging.info("Issue with CoinGecko")
    connectfail=True
    geckojson={}
  return geckojson, connectfail

def human_format(num):
  num = float('{:.3g}'.format(num))
  magnitude = 0
  while abs(num) >= 1000:
    magnitude += 1
    num /= 1000.0
  return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])

def internet(hostname="google.com"):
  """
  Host: google.com
  """
  try:
    # see if we can resolve the host name -- tells us if there is
    # a DNS listening
    host = socket.gethostbyname(hostname)
    # connect to the host -- tells us if the host is actually
    # reachable
    s = socket.create_connection((host, 80), 2)
    s.close()
    return True
  except:
    logging.info("Google says No")
    time.sleep(1)
  return False

def makeSpark(pricestack):
  # Draw and save the sparkline that represents historical data
  # Subtract the mean from the sparkline to make the mean appear on the plot (it's really the x axis)
  themean= sum(pricestack)/float(len(pricestack))
  x = [xx - themean for xx in pricestack] 
  fig, ax = plt.subplots(1,1,figsize=(10,3))
  plt.plot(x, color='k', linewidth=6)
  plt.plot(len(x)-1, x[-1], color='r', marker='o')
  # Remove the Y axis
  for k,v in ax.spines.items():
    v.set_visible(False)
  ax.set_xticks([])
  ax.set_yticks([])
  ax.axhline(c='k', linewidth=4, linestyle=(0, (5, 2, 1, 2)))
  # Save the resulting bmp file to the images directory
  plt.savefig(os.path.join(picdir,'spark.png'), dpi=17)
  #imgspk = Image.open(os.path.join(picdir,'spark.png'))
  #file_out = os.path.join(picdir,'spark.bmp')
  #imgspk.save(file_out) 
  plt.clf() # Close plot to prevent memory error
  ax.cla() # Close axis to prevent memory error
  #imgspk.close()
  return

def start(config, lastcoinfetch):
  while internet() == False:
    logging.info("Waiting for Internet")
  logging.info("Connected to the Internet")
  lastgrab = fullupdate(config,lastcoinfetch)
  return

def updateDisplay(config,pricestack,other,crypto,fiat):
  """
  Takes the price data, the desired coin/fiat combo along with the config info for formatting
  if config is re-written following adustment we could avoid passing the last two arguments as
  they will just be the first two items of their string in config
  """
  with open(configfile) as f:
    originalconfig = yaml.load(f, Loader=yaml.FullLoader)
  originalcoin=originalconfig['ticker']['currency']
  originalcoin_list = originalcoin.split(",")
  originalcoin_list = [x.strip(' ') for x in originalcoin_list]
  whichcoin = crypto
  days_ago=int(config['ticker']['sparklinedays'])   
  symbolstring=currency.symbol(fiat.upper())
  if fiat=="jpy" or fiat=="cny":
    symbolstring="¥"
  pricenow = pricestack[-1]
  if config['display']['inverted'] == True:
    currencythumbnail= 'currency/'+whichcoin+'INV.bmp'
  else:
    currencythumbnail= 'currency/'+whichcoin+'.bmp'
  tokenfilename = os.path.join(picdir,currencythumbnail)
  sparkpng = Image.open(os.path.join(picdir,'spark.png'))
  ATHbitmap= Image.open(os.path.join(picdir,'ATH.bmp'))
# Check for token image, if there isn't one, get on off coingecko, resize it and pop it on a white background
  if os.path.isfile(tokenfilename):
    logging.info("Getting token Image from Image directory")
    tokenimage = Image.open(tokenfilename).convert("RGBA")
  else:
    logging.info("Getting token Image from Coingecko")
    tokenimageurl = "https://api.coingecko.com/api/v3/coins/"+whichcoin+"?tickers=false&market_data=false&community_data=false&developer_data=false&sparkline=false"
    rawimage = requests.get(tokenimageurl, headers=headers).json()
    tokenimage = Image.open(requests.get(rawimage['image']['large'], headers = headers, stream=True).raw).convert("RGBA")
    resize = 100,100
    tokenimage.thumbnail(resize, Image.ANTIALIAS)
    # If inverted is true, invert the token symbol before placing if on the white BG so that it is uninverted at the end - this will make things more 
    # legible on a black display
    if config['display']['inverted'] == True:
      #PIL doesnt like to invert binary images, so convert to RGB, invert and then convert back to RGBA
      tokenimage = ImageOps.invert( tokenimage.convert('RGB') )
      tokenimage = tokenimage.convert('RGBA')
    new_image = Image.new("RGBA", (120,120), "WHITE") # Create a white rgba background with a 10 pixel border
    new_image.paste(tokenimage, (10, 10), tokenimage)   
    tokenimage=new_image
    tokenimage.thumbnail((100,100),Image.ANTIALIAS)
    tokenimage.save(tokenfilename)
  pricechangeraw = round((pricestack[-1]-pricestack[0])/pricestack[-1]*100,2)
  if pricechangeraw >= 100:
    pricechange = str("%+d" % pricechangeraw)+"%"
  else:
    pricechange = str("%+.2f" % pricechangeraw)+"%"
  if pricenow > 1000:
    pricenowstring =format(int(pricenow),",")
  else:
    # Print price to 5 significant figures
    pricenowstring =str(float('%.5g' % pricenow))
  if config['display']['orientation'] == 0 or config['display']['orientation'] == 180 :
    image = Image.new('L', (176,264), 255)    # 255: clear the image with white
    draw = ImageDraw.Draw(image)              
    draw.text((110,80),str(days_ago)+"day :",font =font_date,fill = 0)
    draw.text((110,95),pricechange,font =font_date,fill = 0)
    writewrappedlines(image, symbolstring+pricenowstring,40,65,8,10,"Roboto-Medium" )
    draw.text((10,10),str(time.strftime("%-I:%M %p, s%d %b %Y")),font =font_date,fill = 0)
    image.paste(tokenimage, (10,25))
    image.paste(sparkpng,(10,125))
    if config['display']['orientation'] == 180 :
      image=image.rotate(180, expand=True)
  if config['display']['orientation'] == 90 or config['display']['orientation'] == 270 :
    image = Image.new('L', (264,176), 255)    # 255: clear the image with white
    draw = ImageDraw.Draw(image) 
    if other['ATH']==True:
      image.paste(ATHbitmap,(190,85))  
    draw.text((110,90),str(days_ago)+" day : "+pricechange,font =font_date,fill = 0)
    if 'showvolume' in config['display'] and config['display']['showvolume']:
      draw.text((110,105),"24h vol : " + human_format(other['volume']),font =font_date,fill = 0)
    writewrappedlines(image, symbolstring+pricenowstring,50,55,8,10,"Roboto-Medium" )
    image.paste(sparkpng,(80,40))
    image.paste(tokenimage, (0,10))
    # Don't show rank for #1 coin, #1 doesn't need to show off                  
    if 'showrank' in config['display'] and config['display']['showrank'] and other['market_cap_rank'] > 1:
      draw.text((10,105),"Rank: " + str("%d" % other['market_cap_rank']),font =font_date,fill = 0)
    if (config['display']['trendingmode']==True) and not (str(whichcoin) in originalcoin_list):
      draw.text((95,28),whichcoin,font =font_date,fill = 0)
#   draw.text((5,110),"In retrospect, it was inevitable",font =font_date,fill = 0)
    draw.text((95,15),str(time.strftime("%-I:%M %p, %d %b %Y")),font =font_date,fill = 0)
    if config['display']['orientation'] == 270 :
      image=image.rotate(180, expand=True)
#   This is a hack to deal with the mirroring that goes on in older waveshare libraries Uncomment line below if needed
#   image = ImageOps.mirror(image)
# If the display is inverted, invert the image usinng ImageOps        
  if config['display']['inverted'] == True:
    image = ImageOps.invert(image)
# Return the ticker image
  return image

def writewrappedlines(img,text,fontsize=16,y_text=20,height=15, width=25,fontstring="Roboto-Light"):
  lines = textwrap.wrap(text, width)
  numoflines=0
  for line in lines:
    _place_text(img, line,0, y_text, fontsize,fontstring)
    y_text += height
    numoflines+=1
  return img

app = App(title="CryptoCurrency Ticker", layout="grid")
app.set_full_screen()

logging.info("Starting ticker...")
with open(configfile) as f:
  config = yaml.load(f, Loader=yaml.FullLoader)
logging.info(config)
staticcoins = config['ticker']['currency']
staticcoins_list = currencystringtolist(staticcoins)
fiat_list = currencystringtolist(config['ticker']['fiatcurrency'])
howmanycoins = len(config['ticker']['currency'].split(','))

startimg = Image.new('L', (264, 176), 255)
startdraw = ImageDraw.Draw(startimg)
startdraw.text((95, 15), "Starting up...", font=font_date, fill=0)

lastcoinfetch = time.time()

crypto_choice = Combo(app, options=staticcoins_list, grid=[0,0], align="left", width=25)
fiat_choice = Combo(app, options=fiat_list, grid=[1,0], align="right", width=25)
center_image = Picture(app, image=startimg, grid=[0,1,2,1])
button_fu = PushButton(app, command=fullupdate, args=[config, lastcoinfetch], text="Render", grid=[1,2], align="right")

def main(loglevel=logging.WARNING):
  #loglevel = logging.DEBUG
  logging.basicConfig(level=loglevel)

  global app
  global config
  global staticcoins_list
  global fiat_list
  global lastcoinfetch

  try:
    config['display']['orientation'] = int(config['display']['orientation'])
    datapulled = False
    if int(config['ticker']['updatefrequency']) < 180:
      logging.info("Throttling update frequency to 180 seconds")
      updatefrequency = 180
    else:
      updatefrequency = int(config['ticker']['updatefrequency'])

    app.after(5, start, args=[config, lastcoinfetch])
    app.repeat(updatefrequency*1000, fullupdate, args=[config, lastcoinfetch])
    app.display()
  except (IOError, Exception) as e:
    logging.info(e)
    image = beanaproblem(str(e)+" Line: "+str(e.__traceback__.tb_lineno))
    display_image(image)
  except KeyboardInterrupt:
    logging.info("ctrl + c:")
    image = beanaproblem("Keyboard Interrupt")
    display_image(image)
    exit()

if __name__ == '__main__':
  main()
