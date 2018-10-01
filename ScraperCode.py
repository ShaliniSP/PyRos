
# coding: utf-8

# In[1]:

import requests
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import pickle
from time import sleep


#get_ipython().magic("config InlineBackend.figure_format = 'retina'")
#get_ipython().magic('matplotlib inline')

#sns.set_style('white')


# In[ ]:

def request(msg, slp=1):
    '''A wrapper to make robust https requests.'''
    status_code = 500  # Want to get a status-code of 200
    while status_code != 200:
        sleep(slp)  # Don't ping the server too often
        try:
            r = requests.get(msg)
            status_code = r.status_code
            if status_code != 200:
                print ("Server Error! Response Code {}. Retrying...".format(r.status_code))
        except:
            print ("An exception has occurred, probably a momentory loss of connection. Waiting one seconds...")
            sleep(1)
    return r

# Initialize a DF to hold all our scraped game info
games = pd.DataFrame(columns=["gameid", "gamename", "nratings","gamerank"])
min_nratings = 100000 # Set to a high number to satisfy while condition
npage = 1

# Scrape successful pages in the results until we get down to games with < 1000 ratings each
while min_nratings > 1500:
    # Get full HTML for a specific page in the full listing of boardgames sorted by 
    r = request("https://boardgamegeek.com/browse/boardgame/page/{}?sort=numvoters&sortdir=desc".format(npage))
    soup = BeautifulSoup(r.text, "html.parser")    
    
    # Get rows for the table listing all the games on this page. 100 per page
    table = soup.find_all("tr", attrs={"id": "row_"})
    # DF to hold this page's results
    temp_df = pd.DataFrame(columns=["gameid", "gamename", "nratings", "gamerank"], index=range(len(table)))  
    
    # Loop through each row and pull out the info for that game
    for idx, row in enumerate(table):
        links = row.find_all("a")
        try:
            gamerank = links[0]['name'] #Get rank of game
        except Exception: # Expansions will not have ranks and will be recorded as NaN rows in our dataframe
            continue
        gamelink = links[1]  # Get the relative URL for the specific game
        gameid = int(gamelink["href"].split("/")[2])  # Get the game ID by parsing the relative URL
        gamename = links[2].contents[0]  # Get the actual name of the game as the link contents

        ratings_str = row.find_all("td", attrs={"class": "collection_bggrating"})[2].contents[0]
        #split on white space to leave list of string of number, join on empty space then change to int datatype
        nratings = int("".join(ratings_str.split()))
        temp_df.iloc[idx, :] = [gameid, gamename, nratings, gamerank] #Add to temp_df
        
    # Concatenate the results of this page to the master dataframe
    min_nratings = temp_df["nratings"].min()  # The smallest number of ratings of any game on the page
    print ("Page {} scraped, minimum number of ratings was {}".format(npage, min_nratings))
    games = pd.concat([games, temp_df], axis=0)
    npage += 1
    sleep(2) # Keep the BGG server happy.
    
games.dropna(inplace=True)
# Reset the index since we concatenated a bunch of DFs with the same index into one DF
games.reset_index(inplace=True, drop=True)
# Write the DF to .csv for future use
games.to_csv("bgg_gamelist.csv", index=False, encoding="utf-8")

print ("Number of games with > 1000 ratings is approximately {}".format(len(games)))
print ("Total number of ratings from all these games is {}".format(games["nratings"].sum()))

# Create a column for number of full pages for each game
games["nfullpages"] = games["nratings"]//100

# Create the database and make a cursor to talk to it.
import sqlite3
connex = sqlite3.connect("bgg_ratings.db")  # Opens file if exists, else creates file
cur = connex.cursor()

#############################################################
# Gathering all ratings from all games in data set
#############################################################
# Get ratings page-by-page for all games, but do it in chunks of 150 games
for nm, grp in games.groupby(np.arange(len(games))//150):
    # Initialize a DF to hold all the responses for this chunk of games
    df_ratings = pd.DataFrame(columns=["gameid", "username", "rating"], index=range(grp["nratings"].sum()+100000))

    # Initialize indices for writing to the ratings dataframe
    dfidx_start = 0
    dfidx = 0
    
    # For this group of games, make calls until all FULL pages of every game have been pulled
    pagenum = 1
    while len(grp[grp["nfullpages"] > 0]) > 0: 
        # Get a restricted DF with only still-active games (have ratings pages left)
        active_games = grp[grp["nfullpages"] > 0]

        # Set the next chunk of the DF "gameid" column using the list of game IDs
        id_list = []
        for game in active_games["gameid"]:
            id_list += [game]*100
        dfidx_end = dfidx_start + len(active_games)*100
        df_ratings.iloc[dfidx_start:dfidx_end, df_ratings.columns.get_loc("gameid")] = id_list

        # Make the request with the list of all game IDs that have ratings left
        id_strs = [str(gid) for gid in active_games["gameid"]]
        gameids = ",".join(id_strs)
        sleep(1.5)  # Keep the server happy
        r = request("http://www.boardgamegeek.com/xmlapi2/thing?id=%s&ratingcomments=1&page=%i" % (gameids, pagenum))        
        soup = BeautifulSoup(r.text, "xml")
        comments = soup("comment")

        # Parse the response and assign it into the dataframe
        l1 = [0]*len(active_games)*100
        l2 = [0]*len(active_games)*100
        j = 0
        for comm in comments:
            l1[j] = comm["username"]
            l2[j] = float(comm["rating"])
            j += 1
        df_ratings.iloc[dfidx_start:dfidx_end, df_ratings.columns.get_loc("username")] = l1
        df_ratings.iloc[dfidx_start:dfidx_end, df_ratings.columns.get_loc("rating")] = l2

        
        grp["nfullpages"] -= 1  # Decrement the number of FULL pages of each game id
        dfidx_start = dfidx_end     
        pagenum += 1  
        print("pagenum updated to %i" %(pagenum,))
        #if (i%100==0):
            
    
    # Strip off the empty rows
    df_ratings = df_ratings.dropna(how="all")
    # Write this batch of all FULL pages of ratings for this chunk of games to the DB
    df_ratings.to_sql(name="ratings", con=connex, if_exists="append", index=False)    
    print("Processed ratings for batch #%i of games." % (nm))

#############################################################
# Request the final partial page of ratings for each game
#############################################################
# Restore the correct number of FULL pages
games["nfullpages"] = games["nratings"]//100 

# Initialize a DF to hold all the responses over all the chunks of games
temp_ratings = pd.DataFrame(columns=["gameid", "username", "rating"], index=range(len(games)*100))

# Initialize indices for writing to the ratings dataframe
dfidx_start = 0
dfidx = 0

# Loop through game-by-game and request the final page of ratings for each game
for idx, row in games.iterrows():
    # Get the game ID and the last page number to request
    pagenum = row["nfullpages"] + 1
    gameid = row["gameid"]
    
    # Make the request for just the last page of ratings of this game
    sleep(1)  # Keep the server happy
    r = requests.get("http://www.boardgamegeek.com/xmlapi2/thing?id={}&ratingcomments=1&page={}".format(gameid, pagenum))
    while r.status_code != 200:
        sleep(2)  # Keep the server happy
        print("Server Error! Response Code %i. Retrying..." % (r.status_code))
        r = requests.get("http://www.boardgamegeek.com/xmlapi2/thing?id=[]&ratingcomments=1&page={}".format(gameid, pagenum))
    soup = BeautifulSoup(r.text, "xml")
    comments = soup("comment")

    # Set the next chunk of the DF "gameids" column with this gameid
    id_list = [gameid]*len(comments)
    dfidx_end = dfidx_start + len(comments)
    temp_ratings.iloc[dfidx_start:dfidx_end, temp_ratings.columns.get_loc("gameid")] = id_list

    # Parse the response and assign it into the dataframe
    l1 = [0]*len(comments)
    l2 = [0]*len(comments)
    j = 0
    for comm in comments:
        l1[j] = comm["username"]
        l2[j] = float(comm["rating"])
        j += 1
    temp_ratings.iloc[dfidx_start:dfidx_end, temp_ratings.columns.get_loc("username")] = l1
    temp_ratings.iloc[dfidx_start:dfidx_end, temp_ratings.columns.get_loc("rating")] = l2

    dfidx_start = dfidx_end   # Increment the starting index for next round        

    if idx%100 == 0:
        print("Finished with a chunk of 100 games.")
        
# Strip off the empty rows
temp_ratings = temp_ratings.dropna(how="all")

# Write this final batch of all partial pages of ratings for this chunk of games to the DB
temp_ratings.to_sql(name="ratings", con=connex, if_exists="append", index=False)
temp_ratings.to_csv(name="ratings.csv", con=connex, if_exists="append", index=False)

# Save our changes and close the connection
connex.commit()
connex.close()

