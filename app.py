import requests
import json
from bs4 import BeautifulSoup
from flask import Flask, render_template, url_for, request
app = Flask(__name__)

# TODO
# 3. Styling

def rjson():
    inputF = open('manga.json', 'r')
    data = json.load(inputF)
    inputF.close()
    return data

def wjson(data):
    outputF = open('manga.json', 'w')
    json_data = json.dumps(data, indent=4)
    outputF.write(json_data)
    outputF.close()
    return json_data

def getTaadUpdates():
    res = []
    main_page = requests.get("https://www.taadd.com/list/New-Update")
    if main_page.status_code == 200:
        soup = BeautifulSoup(main_page.content, 'html.parser')
        soup.prettify()
        updates = soup.find_all('div', class_='intro')
        for u in updates:
            mangaDict = {}
            a = u.find_all('a')[1].get_text()
            try:
                ind = a.lower().index(" ch")
            except ValueError:
                continue
            if ind is None:
                print(ind)
                continue
            name = a[:ind]
            mangaDict['name'] = name
            temp = a[ind:]
            for char in temp:
                if char.isdigit():
                    temp = temp[temp.index(char):]
                    break
                chapter = temp[:temp.index(" ")]
                mangaDict['chapter'] = chapter
                res.append(mangaDict)
    return res


def getReadmngUpdates():
    res = []
    main_page = requests.get("https://readmng.com/latest-releases")
    if main_page.status_code == 200:
        soup = BeautifulSoup(main_page.content, 'html.parser')
        soup.prettify()
        updates = soup.find('div', class_='manga_updates')
        updated = updates.find_all('a')
        name = ""
        chapter = ""
        for i in range(len(updated)):
            title = updated[i].get_text()
            dash = ' - '
            if dash in title:
                ind = title.index(' - ')
                if name != title[0:ind]:
                    mangaDict = {}
                    newName = title[0:ind]
                    mangaDict['name'] = newName
                    newChapter = title[ind + 3:]
                    mangaDict['chapter'] = newChapter
                    name = newName
                    res.append(mangaDict)
                else:
                    continue
            else:
                continue
        return res


@app.route('/')
def root():
    data = rjson()
    return render_template('index.html', data=data)

@app.route('/updates')
def updates():
    data = rjson()
    taad = getTaadUpdates()
    readmng = getReadmngUpdates()
    res = []
    for t in taad:
        for r in readmng:
            if t['name'].lower() == r['name'].lower():
                if r['chapter'] < t['chapter']:
                    r['chapter'] = t['chapter']
        if t not in readmng:
            readmng.append(t)

    for d in data:
        for r in readmng:
            if r['name'].lower() == d['name'].lower():
                if d['chapter'] < r['chapter']:
                    mangaDict = {}
                    print("Updated: " + r['name'] + " " +
                          d['chapter'] + " => " + r['chapter'])
                    mangaDict['name'] = r['name']
                    mangaDict['newchapter'] = r['chapter']
                    mangaDict['oldchapter'] = d['chapter']
                    d['chapter'] = r['chapter']
                    res.append(mangaDict)

    wjson(data)
    return render_template('index.html', data=data, updates=res)

@app.route('/remove', methods=["POST"])
def remove():
    data = rjson()
    print(data)
    name = request.form.to_dict().keys()
    count = 0
    for n in name:
        name = n
    for d in data:
        if d['name'].lower() == name.lower():
            break
        count += 1
    data.pop(count)
    wjson(data)
    return render_template('index.html', data=data)

@app.route('/add', methods=["POST"])
def add():
    data = rjson()
    mangaDict = {}
    name = request.form['manganame']
    for d in data:
        if d['name'].lower() == name.lower():
            return 0
    mangaDict['name'] = name
    mangaDict['chapter'] = "0"
    data.append(mangaDict)
    wjson(data)
    return render_template('index.html', data=data)