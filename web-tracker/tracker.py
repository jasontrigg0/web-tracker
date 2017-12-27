#!/usr/bin/env python
import jtutils
import sys
import pcsv.any2csv
import datetime
import os
import io
import scrape
import pawk

class WebTracker(object):
    def __init__(self,title):
        self.title
    def run(self):
        out = self.fetch()
        trigger = self.trigger(out)
        if trigger not in [True, False, 0, 1]: raise #trigger should be a boolean
        if trigger:
            self.notify(out)
        self.log(out, trigger)
    def log(self, contents, trigger):
        self.make_log_dir()
        YYYYMMDD = datetime.datetime.now().strftime("%Y%m%d")
        HHMMSS = datetime.datetime.now().strftime("%H%M%S")
        trigger_val = trigger * 1
        filename = "{self.title}_{YYYYMMDD}_{HHMMSS}_{trigger_val}.log".format(**vars())
        full_path = os.path.join(self.get_log_dir(), filename)
        with open(full_path,'w') as fout:
            fout.write(contents)
        self.cleanup_logs()
    def cleanup_logs(self):
        #keep only the most recent run and the most recent triggered run
        all_logs = self.get_all_logfiles()
        trigger_logs = [l for l in all_logs if self.is_trigger(l)]
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
    def is_trigger(self,log_file_name):
        return int(log_file_name.rsplit(".",1)[0].rsplit("_",3)[3]) #requires trigger=1 from "title_YYYYMMDD_HHMMSS_trigger.log"
    def get_last_trigger(self):
        logs = [l for l in self.get_all_logfiles() if self.is_trigger(l)]
        if len(logs) == 0:
            return None
        else:
            with open(logs[0]) as f_in:
                return f_in.read()
    def notify(self, val):
        email("Trigger value {val} occurred for tracker {self.title}! [eom]".format(**vars()),"")
    def cmd2df(self, cmd):
        out, _, _ = jtutils.run(cmd)
        df = pcsv.any2csv.csv2df(out)
        return df
    def trigger_increase(self, fetch_val):
        last_fetch_val = self.get_last_trigger()
        print(fetch_val, last_fetch_val)
        return (not last_fetch_val) or (float(fetch_val) > float(last_fetch_val))
    def trigger_change(self, fetch_val, threshold):
        last_fetch_val = self.get_last_trigger()
        return (not last_fetch_val) or (abs(float(fetch_val) - float(last_fetch_val)) > threshold)
    def trigger(self, fetch_val):
        if not fetch_val:
            raise Exception("Invalid fetch_val: " + str(fetch_val))
        return self.trigger_increase(fetch_val)


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
                                 "grep_code":'i>2 and "%" not in r[0]'
        })

        df = pcsv.any2csv.csv2df(pawk_output)
        top_rating = str(df["Rating"].iloc[0])
        return top_rating
    def notify(self, val):
        email("CCRL high rating!", "New top rating: {val}. {self.url}".format(**vars()))

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
                                 "grep_code":'len(r) > 0 and (i==0 or r[0])',
                                 "process_code":['if i == 0: r = r[6:]; end; write_line(r[:31])']
        })
        df = pcsv.any2csv.csv2df(pawk_output)
        threes = str(df["3PA"].iloc[0])
        return threes
    def notify(self, val):
        email("BBR record 3PA!", "New record: {val}. {self.url}".format(**vars()))

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
        max_rating = str(df["Rating"].iloc[0])
        return max_rating
    def notify(self, val):
        email("CGS record go elo!", "New record: {val}. {self.url}".format(**vars()))

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
            "grep_code":'len(r) > 0 and (i==0 or r[0])',
            "process_code":['if i == 0: r = r[3:]; end; write_line(r[:20])']})
        df = pcsv.any2csv.csv2df(pawk_output)
        max_rating = str(max(df["Rate"]))
        return max_rating
    def notify(self, val):
        email("New record NFL passer rating!", "New record: {val}. {self.url}".format(**vars()))

class Cryptos(WebTracker):
    def __init__(self):
        super(Cryptos,self)
        self.title = "cryptos"
        self.url = "https://coinmarketcap.com/"
    def fetch(self):
        scrape_output = scrape.scrape({"url":self.url,
                                       "css":'div#total_market_cap',
                                       "text":True})
        marketcap = pawk.pawk({
            "input":scrape_output,
            "process_code":['l = l.replace(",",""); l = re.findall("[0-9]+",l); if l: print(l[0]); ']
        })
        if not marketcap:
            raise Exception("Couldn't find marketcap!\n" + cmd)
        return marketcap
    def notify(self, val):
        email("New record crypto marketcap!", "New record: {val}. {self.url}".format(**vars()))

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
    def trigger(self, val):
        return self.trigger_change(val, 0) #trigger whenever the percent changes by even 1%
    def notify(self, val):
        email("Movement in Donald Trump 2018 market!", "New value: {val}. {self.url}".format(**vars()))

class GoogleNapoleon(WebTracker):
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
    def trigger(self, val):
        return val != "Napoleon"
    def notify(self, val):
        email("Google knows Napoleon didn't win the Battle of Waterloo!", "It says {val} won.".format(**vars()))

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
    def trigger(self, new_csv):
        last_trigger = self.get_last_trigger()
        if not last_trigger:
            return True
        df = pcsv.any2csv.csv2df(last_trigger)
        old_titles = set(df["Title"].values)
        new_df = pcsv.any2csv.csv2df(new_csv)
        YYYY = datetime.datetime.now().strftime("%Y")
        #filter for films that weren't on the old film list and was released this year or last
        #reduce=True from here:
        #https://stackoverflow.com/questions/11418192/pandas-complex-filter-on-rows-of-dataframe
        new_titles = new_df[new_df.apply(lambda x: x["Title"] not in old_titles and int(YYYY) - int(x["Year"]) <= 1, axis=1, reduce=True)]
        return len(new_titles) > 0

class IMDBMovie(IMDBTop):
    def __init__(self):
        super(IMDBMovie,self)
        self.title = "imdbmovie"
        self.url = "http://www.imdb.com/chart/top"
    def notify(self, val):
        email("New movie on IMDB top 250!", "{self.url}".format(**vars())) #TODO tell the email which movie it is!

class IMDBTv(IMDBTop):
    def __init__(self):
        super(IMDBTv,self)
        self.title = "imdbtv"
        self.url = "http://www.imdb.com/chart/toptv/"
    def notify(self, val):
        email("New tv show on IMDB top 250!", "{self.url}".format(**vars())) #TODO tell the email which show it is!

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
    ]:
        print(tracker.url)
        tracker.run()

def email(subject, body):
    #TODO: proper unix escaping
    #TODO: failed commands should throw exceptions
    subject = subject.replace("'","'\\''")
    body = body.replace("'", "'\\''")
    jtutils.run("gmail.py -t jasontrigg0@gmail.com -s '{subject}' -b '{body}'".format(**vars()))

if __name__ == "__main__":
    run_all()
