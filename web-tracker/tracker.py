#!/usr/bin/env python
import jtutils
import sys
import pcsv.any2csv
import datetime
import os
import io
import scrape
import pawk
import json

class WebTracker(object):
    def __init__(self,title):
        self.title
    def run(self):
        #trigger_val: boolean
        #notify_args: dict
        #new_state: string
        trigger_val, notify_args, new_state = self.update()
        if trigger_val not in [True, False, 0, 1]: raise #trigger should be a boolean, check compute_trigger() function
        if trigger_val:
            self.notify(**notify_args)
        self.log(new_state, trigger_val)
    def update(self):
        #update defines the function to take the prior state
        #(by default self.get_last_trigger())
        #and the new information
        #(self.fetch())
        #and decide whether to trigger
        #and what the new_state is

        #TODO: can I remove references to self.fetch_val?
        #could those be handled by a different update function
        self.fetch_val = self.fetch()
        return (self.compute_trigger(), {"fetch_val": self.fetch_val}, self.fetch_val)
    def log(self, contents, trigger_val):
        self.make_log_dir()
        YYYYMMDD = datetime.datetime.now().strftime("%Y%m%d")
        HHMMSS = datetime.datetime.now().strftime("%H%M%S")
        trigger_val = trigger_val * 1
        filename = "{self.title}_{YYYYMMDD}_{HHMMSS}_{trigger_val}.log".format(**vars())
        full_path = os.path.join(self.get_log_dir(), filename)
        with open(full_path,'w') as fout:
            fout.write(contents)
        self.cleanup_logs()
    def cleanup_logs(self):
        #keep only the most recent run and the most recent triggered run
        all_logs = self.get_all_logfiles()
        trigger_logs = [l for l in all_logs if self.is_log_file_trigger(l)]
        for l in all_logs:
            last_log = (not all_logs) or l == all_logs[0]
            last_trigger_log = (not trigger_logs) or l == trigger_logs[0]
            if (not last_log) and (not last_trigger_log):
                os.remove(l)
                continue
    def make_log_dir(self):
        directory = self.get_log_dir()
        if not os.path.exists(directory):
            os.makedirs(directory)
    def get_log_dir(self):
        from os.path import expanduser
        home = expanduser("~")
        directory = os.path.join(home, ".tracker", self.title)
        return directory
    def get_all_logfiles(self):
        self.make_log_dir()
        log_dir = self.get_log_dir()
        logs = [os.path.join(log_dir,f) for f in os.listdir(log_dir) if f.endswith("log")] #return the full path
        return sorted(logs, reverse=True) #from newest to oldest
    def get_last_logfile():
        logs = self.get_all_logfiles()
        if len(logs) == 0:
            return None
        else:
            return logs[0]
    def is_log_file_trigger(self,log_file_name):
        return int(log_file_name.rsplit(".",1)[0].rsplit("_",3)[3]) #requires trigger=1 from "title_YYYYMMDD_HHMMSS_trigger.log"
    def get_last_trigger(self):
        #most recent logfile that was a trigger
        logs = [l for l in self.get_all_logfiles() if self.is_log_file_trigger(l)]
        if len(logs) == 0:
            return None
        else:
            with open(logs[0]) as f_in:
                return f_in.read()
    def notify(self, **args):
        email("Trigger value {args.fetch_val} occurred for tracker {self.title}! [eom]".format(**vars()),"")
    def cmd2df(self, cmd):
        out, _, _ = jtutils.run(cmd)
        df = pcsv.any2csv.csv2df(out)
        return df
    def trigger_increase(self):
        last_fetch_val = self.get_last_trigger()
        print(self.fetch_val, last_fetch_val)
        return (not last_fetch_val) or (float(self.fetch_val) > float(last_fetch_val))
    def trigger_abs_change(self, threshold):
        last_fetch_val = self.get_last_trigger()
        return (not last_fetch_val) or (abs(float(self.fetch_val) - float(last_fetch_val)) > threshold)
    def trigger_pct_change(self, threshold):
        #trigger on a minimum percent change
        #eg trigger_pct_change(10) to trigger once the value has gone up or down by 10%
        last_fetch_val = self.get_last_trigger()
        return (not last_fetch_val) or (100 * abs(float(self.fetch_val) - float(last_fetch_val))/float(last_fetch_val) > threshold)
    def trigger_diff(self):
        last_fetch_val = self.get_last_trigger()
        return (not last_fetch_val) or (last_fetch_val != self.fetch_val)
    def compute_trigger(self):
        if not self.fetch_val:
            raise Exception("Invalid fetch_val: " + str(self.fetch_val))
        return self.trigger_diff()


class CCRL(WebTracker):
    def __init__(self):
        super(CCRL,self)
        self.title = "ccrl"
        self.url = "http://www.computerchess.org.uk/ccrl/4040/"
    def fetch(self):
        scrape_output = scrape.scrape({"url":self.url,
                                       "table":True,
                                       "grep":"Rank",
                                       "index":1
        })
        pawk_output = pawk.pawk({"input":scrape_output,
                                 "begin_code":['print("Rank,Name,Rating,,,Score,AverageOpponent,Draws,Games")'],
                                 "grep_code":'i>1 and "%" not in r[0]'
        })

        df = pcsv.any2csv.csv2df(pawk_output)
        top_rating = str(df["Rating"].iloc[0])
        return top_rating
    def compute_trigger(self):
        return self.trigger_increase()
    def notify(self, **args):
        email("CCRL high rating!", "New top rating: {self.fetch_val}. {self.url}".format(**vars()))

class BBR(WebTracker):
    def __init__(self):
        super(BBR,self)
        self.title = "BBR"
        self.url = "https://www.basketball-reference.com/leagues/NBA_stats.html"
    def fetch(self):
        scrape_output = scrape.scrape({"url":self.url,
                                       "table":True,
                                       "index":0})
        pawk_output = pawk.pawk({"input":scrape_output,
                                 "grep_code":'i==1 or (r[0] and r[0] != "Rk")',
                                 "process_code":['if i == 0: r = r[6:]; end; write_line(r[:31])']
        })
        df = pcsv.any2csv.csv2df(pawk_output)
        threes = str(df["3PA"].iloc[0])
        return threes
    def compute_trigger(self):
        return self.trigger_increase()
    def notify(self, **args):
        fetch_val = args["fetch_val"]
        email("BBR record 3PA!", 'New record: {fetch_val}. {self.url}'.format(**vars()))

class CGS(WebTracker):
    def __init__(self):
        super(CGS,self)
        self.title="CGS"
        self.url = "http://www.yss-aya.com/cgos/19x19/standings.html"
    def fetch(self):
        scrape_output = scrape.scrape({"url":self.url,
                                       "table":True,
                                       "index":0})
        df = pcsv.any2csv.csv2df(scrape_output)
        max_rating = str(df["Rating"].iloc[0]).replace("?","") #3997? -> 3997
        return max_rating
    def compute_trigger(self):
        return self.trigger_increase()
    def notify(self, **args):
        email("CGS record go elo!", "New record: {self.fetch_val}. {self.url}".format(**vars()))

class PFR(WebTracker):
    def __init__(self):
        super(PFR,self)
        self.title = "PFR"
        self.url = "https://www.pro-football-reference.com/years/NFL/passing.htm"
    def fetch(self):
        scrape_output = scrape.scrape({"url":self.url,
                                      "table":True,
                                      "index":0})
        pawk_output = pawk.pawk({
            "input":scrape_output,
            "grep_code":'r[0] and (i==1 or r[0] != "Rk")',
        })
        df = pcsv.any2csv.csv2df(pawk_output)
        max_rating = str(max(df["Rate"]))
        return max_rating
    def compute_trigger(self):
        return self.trigger_increase()
    def notify(self, **args):
        email("New record NFL passer rating!", "New record: {self.fetch_val}. {self.url}".format(**vars()))

class Cryptos(WebTracker):
    def __init__(self):
        super(Cryptos,self)
        self.title = "cryptos"
        self.url = 'https://s2.coinmarketcap.com/generated/stats/global.json'
    def fetch(self):
        marketcap = json.loads(jtutils.url_to_soup(self.url).body.p.text)["total_market_cap_by_available_supply_usd"]
        marketcap = str(round(marketcap))

        if not marketcap:
            raise Exception("Couldn't find marketcap!\n")
        return marketcap
    def compute_trigger(self):
        return self.trigger_pct_change(10)
    def notify(self, **args):
        last_trigger = self.get_last_trigger()
        email("Crypto marketcap moving!", "New marketcap: {self.fetch_val}. Old marketcap: {last_trigger}. {self.url}".format(**vars()))

class Trump2018(WebTracker):
    def __init__(self):
        super(Trump2018,self)
        self.title = "trump2018"
        self.url = "https://www.predictit.org/Contract/5367/Will-Donald-Trump-be-president-at-year-end-2018"
    def fetch(self):
        scrape_output = scrape.scrape({"url":self.url,
                                       "css":'div.dashboard > p > strong'})
        pct = pawk.pawk({
            "input":scrape_output,
            "process_code":['print(re.findall("\d+",l)[0])'],
        })
        return pct
    def compute_trigger(self):
        return self.trigger_abs_change(3) #trigger whenever the percent changes by 3%
    def notify(self, **args):
        last_trigger = self.get_last_trigger()
        email("Movement in Donald Trump 2018 market!", "New value: {self.fetch_val}. Last value: {last_trigger}. {self.url}".format(**vars()))

class GoogleNapoleon(WebTracker):
    #Update 20180405: google doesn't say anyone won the battle of waterloo
    def __init__(self):
        super(GoogleNapoleon,self)
        self.title = "googlenapoleon"
        self.url = "https://www.google.com/search?q=who+won+the+battle+of+waterloo"
    def fetch(self):
        out = scrape.scrape({
            "url":self.url,
            "css":'div[data-tts="answers"]',
            "text":True
        })
        return out.strip()
    def compute_trigger(self):
        return self.fetch_val not in ["Napoleon","Napoleon Bonaparte"]
    def notify(self, **args):
        email("Google knows Napoleon didn't win the Battle of Waterloo!", "It says {self.fetch_val} won.".format(**vars()))


class IMDBTop(WebTracker):
    def __init__(self):
        super(IMDBTop,self)
    def fetch(self):
        scrape_output = scrape.scrape({
            "url":self.url,
            "table":True,
            "grep":"Rating"})
        pawk_output = pawk.pawk({
            "input":scrape_output,
            "begin_code":['print("Title")'],
            "grep_code":'i>0',
            "process_code":['r = r[1:]; r[0] = r[0].split("      ")[1]; write_line([r[0]])']
        })
        pcsv_output = pcsv.pcsv({
            "input":pawk_output,
            "process_code":['r["Year"] = re.findall("\((\d{4})\)",r["Title"])[0]'],
        })
        return pcsv_output
    def imdb_diff(self, new_csv):
        last_trigger = self.get_last_trigger()
        df = pcsv.any2csv.csv2df(last_trigger)
        old_titles = set(df["Title"].values)
        new_df = pcsv.any2csv.csv2df(new_csv)
        new_titles = set(new_df["Title"].values)
        YYYY = datetime.datetime.now().strftime("%Y")
        #filter for films that weren't on the old film list and was released this year or last
        #reduce=True from here:
        #https://stackoverflow.com/questions/11418192/pandas-complex-filter-on-rows-of-dataframe
        new_titles = new_df[new_df.apply(lambda x: x["Title"] not in old_titles and int(YYYY) - int(x["Year"]) <= 1, axis=1, reduce=True)].values
        return new_titles
    def compute_trigger(self):
        last_trigger = self.get_last_trigger()
        if not last_trigger:
            return True
        new_titles = self.imdb_diff(self.fetch_val)
        return len(new_titles) > 0


class IMDBMovie(IMDBTop):
    def __init__(self):
        super(IMDBMovie,self)
        self.title = "imdbmovie"
        self.url = "http://www.imdb.com/chart/top"
    def notify(self, **args):
        new_titles = self.imdb_diff(self.fetch_val)
        email("New movie on IMDB top 250!", "{new_titles}".format(**vars())) #TODO tell the email which movie it is!

class IMDBTv(IMDBTop):
    def __init__(self):
        super(IMDBTv,self)
        self.title = "imdbtv"
        self.url = "http://www.imdb.com/chart/toptv/"
    def notify(self, **args):
        new_titles = self.imdb_diff(self.fetch_val)
        email("New tv show on IMDB top 250!", "{new_titles}".format(**vars())) #TODO tell the email which show it is!

class YC(WebTracker):
    def __init__(self):
        super(YC,self)
        self.title="YC"
        self.url="http://www.ycombinator.com/"
    def fetch(self):
        out = scrape.scrape({
            "url":self.url,
            "css":'div.startupLogos a',
            "print_url":True,
        })
        return out
    def diff(self):
        new_vals = self.fetch_val.split("\n")
        last_trigger = self.get_last_trigger()
        old_vals = last_trigger.split("\n") if last_trigger else []
        return (new_vals, old_vals)
    def notify(self, **args):
        new_vals, old_vals = self.diff()
        email("Change in top YC companies!","Added companies: {new_vals}. Removed companies: {old_vals}".format(**vars()))

class ArenaOfValor(WebTracker):
    def __init__(self):
        super(ArenaOfValor,self)
        self.title="ArenaOfValor"
        self.url="http://reddit.com/r/arenaofvalor"
    def fetch(self):
        try:
            #"old reddit"
            out = scrape.scrape({
                "url":self.url,
                "css":"span.subscribers span.number",
                "text":True
            })
            out = out.split("\n")[0].replace(",","")
            return out
        except:
            pass

        #"new reddit"
        soup = jtutils.url_to_soup(self.url,True)
        subs = (soup.find_all(text="Subscribers")[0].parent.parent.find_all('p')[0].text)
        out = (str(int(float(subs.replace('k','')) * 1000)))
        return out
    def compute_trigger(self):
        return self.trigger_pct_change(50)
    def notify(self, **args):
        email("ArenaOfValor subreddit growing!","{self.fetch_val} users.".format(**vars()))

class SteamCharts(WebTracker):
    def __init__(self):
        super(SteamCharts,self)
        self.title="SteamCharts"
        self.url="http://steamcharts.com/"
    def fetch(self):
        out = scrape.scrape({
            "url":self.url,
            "css":'table#top-games td.peak-concurrent',
            "text":True
        })
        out = out.split("\n")[0].replace(",","")
        return out
    def compute_trigger(self):
        return self.trigger_increase()
    def notify(self, **args):
        email("New peak users on steamcharts!","{self.fetch_val} peak concurrent players.".format(**vars()))

class LeelaZero(WebTracker):
    def __init__(self):
        super(LeelaZero, self)
        self.title="LeelaZero"
        self.url="http://zero.sjeng.org/"
    def fetch(self):
        out = scrape.scrape({
            "url":self.url,
            "table":True,
            "css":".networks-table",
            "text":True
        })
        df = pcsv.any2csv.csv2df(out)
        return df.values[1][1]
    def notify(self, **args):
        email("New LeelaZero network!","See: {self.url}".format(**vars()))

class LCZero(WebTracker):
    def __init__(self):
        super(LCZero, self)
        self.title="LCZero"
        self.url="http://lczero.org/networks"
    def fetch(self):
        out = scrape.scrape({
            "url":self.url,
            "table":True,
            "index":0
        })
        df = pcsv.any2csv.csv2df(out)
        return str(df.values[0][2])
    def compute_trigger(self):
        return self.trigger_increase()
    def notify(self, **args):
        email("New best LCZero network!","See: {self.url}".format(**vars()))

class TrackAndField(WebTracker):
    def __init__(self):
        super(TrackAndField, self)
        self.title="TrackAndField"
        self.url=["https://trackandfieldnews.com/records/mens-world-records/","https://trackandfieldnews.com/records/womens-world-records/"]
    def fetch(self):
        mens = scrape.scrape({"url":self.url[0],
                             "table":True,
                             "index":0})
        womens = scrape.scrape({"url":self.url[1],
                                "table":True,
                                "index":1})
        return mens + "\n" + womens
    def notify(self, **args):
        email("New track and field world record","See: {self.url}".format(**vars()))

class Twitch(WebTracker):
    #TODO: figure out trigger
    def __init__(self):
        super(Twitch, self)
        self.title='Twitch'
        self.url= "https://sullygnome.com/games/30/watched"
    def fetch(self):
        table = scrape.scrape({"url": self.url,
                           "table":True,
                           "js":True
        })
        out = pawk.pawk({
            "input":table,
            "grep_code":'i<=5',
            "process_code":['r[3] = r[3].replace("hours","").replace(",",""); write_line(r[2:4])']
        })
        #@example
        #out =
        #Game,Watch time
        #Fortnite,126481107
        #League of Legends,71854484
        #IRL,43996483
        #Dota 2,42668300
        #PLAYERUNKNOWN'S BATTLEGROUNDS,36111039
        return out
    def update(self):
        import pandas as pd
        if self.get_last_trigger():
            df_state = pcsv.any2csv.csv2df(self.get_last_trigger())
            dict_state = dict(df_state.values)
        else:
            dict_state = {}

        fetch_val = self.fetch()
        df_new = pcsv.any2csv.csv2df(fetch_val)
        dict_new = dict(df_new.values)

        trigger = False
        new_highs = {}
        for game in dict_new:
            if int(dict_new[game]) > int(dict_state.get(game,0)):
                trigger = True #a game hit a new high!
                dict_state[game] = dict_new[game]
                new_highs[game] = dict_new[game]

        out = pcsv.any2csv.rows2csv([["game","hours"]] + list(dict_state.items()))
        notify = pcsv.any2csv.rows2csv([["game","hours"]] + list(new_highs.items()))
        return (trigger, {"body": notify}, out)
    def notify(self, **args):
        email("New peak twitch viewing hours!", args["body"])



def run_all():
    for tracker in [
            CCRL(),
            BBR(),
            CGS(),
            PFR(),
            Cryptos(),
            Trump2018(),
            IMDBMovie(),
            IMDBTv(),
            GoogleNapoleon(),
            YC(),
            ArenaOfValor(),
            SteamCharts(),
            LeelaZero(),
            TrackAndField(),
            LCZero(),
            Twitch()
    ]:
        run_tracker(tracker)

def run_tracker(tracker):
    print(tracker.url)
    try:
        tracker.run()
    except:
        import traceback
        traceback.print_exc()

def email(subject, body):
    #TODO: proper unix escaping
    subject = subject.replace("'","'\\''")
    body = body.replace("'", "'\\''")
    jtutils.run("/home/jtrigg/scripts/mailer -t jasontrigg0@gmail.com -s '{subject}' -b '{body}'".format(**vars()))

if __name__ == "__main__":
    run_all()
