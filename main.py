# -*- coding: utf-8 -*-
# Module: default
# Author: Jason Francis
# Created on: 2017-10-15
# Based on plugin.video.example(https://github.com/romanvm/plugin.video.example)
# License: MIT https://opensource.org/licenses/MIT

import sys
from urlparse import parse_qsl
import xbmcgui
import xbmcplugin
import xbmcaddon
import re
import requests
import json
import time
from bs4 import BeautifulSoup
import subprocess

import xbmc

# Get the plugin url in plugin:// notation.
_url = sys.argv[0]
# Get the plugin handle as an integer number.
_handle = int(sys.argv[1])
baseUrl = "https://www.bitchute.com"
playlistPageLength = 25
addon = xbmcaddon.Addon()

class VideoLink:
    def __init__(self):
        self.title = None
        self.pageUrl = None
        self.id = None
        self.thumbnail = None
        self.channelName = None
        self.url = None

    @staticmethod
    def getUrl(videoId):
        req = fetchLoggedIn(baseUrl + "/video/" + videoId)
        soup = BeautifulSoup(req.text, 'html.parser')
        for link in soup.findAll("a", href=re.compile("^magnet")):
            magnetUrl = link.get("href")
            if magnetUrl.startswith("magnet:?"):
                return magnetUrl
        raise ValueError("Could not find the magnet link for this video.")
    def setUrl(self):
        self.url = self.getUrl(videoId)
    @staticmethod
    def getVideoFromChannelVideosContainer(containerSoup):
        video = VideoLink()

        #find the video title and URL
        titleDiv = containerSoup.findAll('div', "channel-videos-title")[0]
        linkSoup = titleDiv.findAll('a')[0]

        video.title = linkSoup.string
        video.pageUrl = linkSoup.get("href")
        video.pageUrl = video.pageUrl.rstrip('/')
        video.id = video.pageUrl.split("/")[-1]

        #before we can find thumnails let's strip out play button images.
        for playButton in containerSoup.findAll('img', "play-overlay-icon"):
            playButton.extract()
        
        thumbnailMatches = containerSoup.findAll('img', "img-responsive")
        if thumbnailMatches:
            video.thumbnail = thumbnailMatches[0].get("data-src")
        return video
    @staticmethod
    def getVideoFromVideoCard(videoSoup):
        video = VideoLink()
        linkSoup = videoSoup.findAll('a')[0]

        video.pageUrl = linkSoup.get("href")
        video.pageUrl = video.pageUrl.rstrip('/')
        video.id = video.pageUrl.split("/")[-1]

        titleSoup = videoSoup.findAll('div', 'video-card-text')[0].findAll('p')[0].findAll('a')[0]
        video.title = titleSoup.text

        thumbnailMatches = videoSoup.findAll('img', "img-responsive")
        if thumbnailMatches:
            video.thumbnail = thumbnailMatches[0].get("data-src")
        #try to find the name of the channel from video-card-text portion of the card.
        try:
            channelNameSoup = videoSoup.findAll('div', 'video-card-text')[0].findAll('p')[1].findAll('a')[0]
            video.channelName = channelNameSoup.get("href").split("/")[-1]
        except:
            pass
        return video
    @staticmethod
    def getVideoFromPlaylist(container):
        video = VideoLink()
        titleSoup = container.findAll('div', 'text-container')[0].findAll('div', 'title')[0].findAll('a')[0]
        video.title = titleSoup.text
        video.pageUrl = titleSoup.get("href").rstrip('/')
        video.id = video.pageUrl.split("/")[-1]
        try:
            channelNameSoup = container.findAll('div', 'text-container')[0].findAll('div', 'channel')[0].findAll('a')[0]
            video.channelName = channelNameSoup.get("href").rstrip('/').split("/")[-1]
        except:
            pass

        for thumb in container.findAll("img", {"class": "img-responsive"}):
            if(thumb.has_attr("data-src")):
                video.thumbnail = thumb.get("data-src")
            break
        return video
    @staticmethod
    def getVideosByPlaylist(playlistId, offset = 0):
        videos = []
        req = postLoggedIn(baseUrl + "/playlist/" + playlistId + "/extend/", baseUrl + "/playlist/" + playlistId, {"offset": offset})
        data = json.loads(req.text)
        soup = BeautifulSoup(data["html"], 'html.parser')
        for container in soup.findAll("div", {"class": "playlist-video"}):
            videos.append(VideoLink.getVideoFromPlaylist(container))
        return videos

class Channel:
    def __init__(self, channelName, pageNumber = None, thumbnail = None):
        self.channelName = channelName
        self.videos = []
        self.thumbnail = thumbnail
        self.page = 1
        if pageNumber is not None:
            self.page = pageNumber
        self.hasPrevPage = False
        self.hasNextPage = False
    
    def setThumbnail(self):
        thumbnailReq = fetchLoggedIn(baseUrl + "/channel/" + self.channelName)
        thumbnailSoup = BeautifulSoup(thumbnailReq.text, 'html.parser')
        thumbnailImages = thumbnailSoup.findAll("img", id="fileupload-medium-icon-2")
        if thumbnailImages and thumbnailImages[0].has_attr("data-src"):
            self.thumbnail = thumbnailImages[0].get("data-src")

    def setPage(self, pageNumber):
        self.videos = []
        self.page = pageNumber
        self.hasPrevPage = False
        self.hasNextPage = False
        
        r = postLoggedIn(baseUrl + "/channel/" + self.channelName + "/extend/", baseUrl + "/channel/" + self.channelName + "/",{"index": (self.page - 1)})
        data = json.loads(r.text)
        soup = BeautifulSoup(data['html'], 'html.parser')

        for videoContainer in soup.findAll('div', "channel-videos-container"):
            self.videos.append(VideoLink.getVideoFromChannelVideosContainer(videoContainer))

        if len(self.videos) >= 10:
            self.hasNextPage = True

class Playlist:
    def __init__(self):
        self.name = None
        self.id = None
        self.thumbnail = None
    @staticmethod
    def getPlaylists():
        playlists = []
        req = fetchLoggedIn(baseUrl + "/playlists/")
        soup = BeautifulSoup(req.text, 'html.parser')
        for container in soup.findAll("div", {"class": "playlist-card"}):
            playlist = Playlist()
            linkSoup = container.findAll('a')[0]
            nameSoup = linkSoup.findAll('span', 'title')[0]
            thumbnailSoup = linkSoup.findAll('img', "img-responsive")[0]
            playlist.name = nameSoup.text
            playlist.id = linkSoup.get("href").rstrip('/').split("/")[-1]
            playlist.thumbnail = thumbnailSoup.get("data-src")
            playlists.append(playlist)
        return playlists

class MyPlayer(xbmc.Player):
    def __init__(self):
        MyPlayer.is_active = True
        print("#MyPlayer#")
    
    def onPlayBackPaused( self ):
        xbmc.log("#Im paused#")
        
    def onPlayBackResumed( self ):
        xbmc.log("#Im Resumed #")
        
    def onPlayBackStarted( self ):
        print("#Playback Started#")
        try:
            print("#Im playing :: " + self.getPlayingFile())
        except:
            print("#I failed get what Im playing#")
            
    def onPlayBackEnded( self ):
        print("#Playback Ended#")
        self.is_active = False
        
    def onPlayBackStopped( self ):
        print("## Playback Stopped ##")
        self.is_active = False
    
    def sleep(self, s):
        xbmc.sleep(s) 
def login():
    #BitChute uses a token to prevent csrf attacks, get the token to make our request.
    r = requests.get(baseUrl)
    csrfJar = r.cookies
    soup = BeautifulSoup(r.text, 'html.parser')
    csrftoken = soup.findAll("input", {"name":"csrfmiddlewaretoken"})[0].get("value")

    #Fetch the user info from settings
    username = xbmcplugin.getSetting(_handle, 'username')
    password = xbmcplugin.getSetting(_handle, 'password')
    post_data = {'csrfmiddlewaretoken': csrftoken, 'username': username, 'password': password}
    headers = {'Referer': baseUrl + "/", 'Origin': baseUrl}
    response = requests.post(baseUrl + "/accounts/login/", data=post_data, headers=headers, cookies=csrfJar)
    authCookies = []
    for cookie in response.cookies:
        authCookies.append({ 'name': cookie.name, 'value': cookie.value, 'domain': cookie.domain, 'path': cookie.path, 'expires': cookie.expires })
    
    #stash our cookies in our JSON cookie jar
    cookiesJson = json.dumps(authCookies)
    addon.setSetting(id='cookies', value=cookiesJson)

    return(authCookies)
    
def getSessionCookie():
    cookiesString = xbmcplugin.getSetting(_handle, 'cookies')
    if cookiesString:
        cookies = json.loads(cookiesString)
    else:
        cookies = login()
    
    #If our cookies have expired we'll need to get new ones.
    now = int(time.time())
    for cookie in cookies:
        if now >= cookie['expires']:
            cookies = login()
            break
    
    jar = requests.cookies.RequestsCookieJar()
    for cookie in cookies:
        jar.set(cookie['name'], cookie['value'], domain=cookie['domain'], path=cookie['path'], expires=cookie['expires'])
    
    return jar

def fetchLoggedIn(url):
    req = requests.get(url, cookies=sessionCookies)
    soup = BeautifulSoup(req.text, 'html.parser')
    loginUser = soup.findAll("ul", {"class":"user-menu-dropdown"})
    if loginUser:
        profileLink = loginUser[0].findAll("a",{"class":"dropdown-item", "href":"/profile/"})
        if profileLink:
            return req
    #Our cookies have gone stale, clear them out.
    xbmcplugin.setSetting(_handle, id='cookies', value='')
    raise ValueError("Not currently logged in.")

def postLoggedIn(url, referer, params):
    #BitChute uses a token to prevent csrf attacks, get the token to make our request.
    csrftoken = None
    for cookie in sessionCookies:
        if cookie.name == 'csrftoken':
            csrftoken = cookie.value
            break

    post_data = {'csrfmiddlewaretoken': csrftoken}
    for param in params:
        post_data[param] = params[param]

    headers = {'Referer': referer, 'Host': 'www.bitchute.com', 'Origin': baseUrl, 'Pragma': 'no-cache', 'Cache-Control': 'no-cache'}
    response = requests.post(url, data=post_data, headers=headers, cookies=sessionCookies)
    return response

def getSubscriptions():
    subscriptions = []
    req = fetchLoggedIn(baseUrl + "/subscriptions")
    soup = BeautifulSoup(req.text, 'html.parser')
    for container in soup.findAll("div", {"class":"subscription-container"}):
        thumbnail = None
        for thumb in container.findAll("img", {"class":"subscription-image"}):
            if thumb.has_attr("data-src"):
                thumbnail = thumb.get("data-src")
                thumbnail = thumbnail.replace("_small.", "_large.")
                break
        for link in container.findAll("a", {"rel":"author"}):
            href = link.get("href").rstrip('/')
            name = href.split("/")[-1]
            subscriptions.append(Channel(name, 1, thumbnail))
    return(subscriptions)

sessionCookies = getSessionCookie()



def defaultMenu():
    listing = []
    subsActivity = xbmcgui.ListItem(label="Subscription Activity")
    subsActivity.setInfo('video', {'title': "Subscription Activity", 'genre': "Subscription Activity"})
    subsActivityUrl = '{0}?action=subscriptionActivity'.format(_url)
    listing.append((subsActivityUrl, subsActivity, True))

    watchLater = xbmcgui.ListItem(label="Watch Later")
    watchLater.setInfo('video', {'title': "Watch Later", 'genre': "Watch Later"})
    watchLaterUrl = '{0}?action=playlist&playlistId=watch-later'.format(_url)
    listing.append((watchLaterUrl, watchLater, True))

    playlists = xbmcgui.ListItem(label="Playlists")
    playlists.setInfo('video', {'title': "Playlists", 'genre': "Playlists"})
    playlistsUrl = '{0}?action=playlists'.format(_url)
    listing.append((playlistsUrl, playlists, True))

    subscriptions = xbmcgui.ListItem(label="Subscriptions")
    subscriptions.setInfo('video', {'title': "Subscriptions", 'genre': "Subscriptions"})
    subscriptionsUrl = '{0}?action=subscriptions'.format(_url)
    listing.append((subscriptionsUrl, subscriptions, True))
    
    #add our listing to kodi
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    xbmcplugin.addSortMethod(_handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(_handle)

def listPlaylists():
    listing = []
    playlists = Playlist.getPlaylists()

    for playlist in playlists:
        list_item = xbmcgui.ListItem(label=playlist.name, thumbnailImage=playlist.thumbnail)
        list_item.setProperty('fanart_image', playlist.thumbnail)
        list_item.setInfo('video', {'title': playlist.name, 'genre': playlist.name})
        url = '{0}?action=playlist&playlistId={1}'.format(_url, playlist.id)
        listing.append((url, list_item, True))
    #add our listing to kodi
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    xbmcplugin.addSortMethod(_handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(_handle)

def getCategories():
    """
    Get the list of video categories.
    Here you can insert some parsing code that retrieves
    the list of video categories (e.g. 'Movies', 'TV-shows', 'Documentaries' etc.)
    from some site or server.
    :return: list
    """
    categories = getSubscriptions()
    return categories

def listCategories():
    """
    Create the list of video categories in the Kodi interface.
    :return: None
    """
    # Create a list for our items.
    listing = []

    # Get video categories
    categories = getCategories()
    
    # Iterate through categories
    for category in categories:
        # Create a list item with a text label and a thumbnail image.
        list_item = xbmcgui.ListItem(label=category.channelName, thumbnailImage=category.thumbnail)
        # Set a fanart image for the list item.
        # Here we use the same image as the thumbnail for simplicity's sake.
        list_item.setProperty('fanart_image', category.thumbnail)
        # Set additional info for the list item.
        # Here we use a category name for both properties for for simplicity's sake.
        # setInfo allows to set various information for an item.
        # For available properties see the following link:
        # http://mirrors.xbmc.org/docs/python-docs/15.x-isengard/xbmcgui.html#ListItem-setInfo
        list_item.setInfo('video', {'title': category.channelName, 'genre': category.channelName})
        # Create a URL for the plugin recursive callback.
        # Example: plugin://plugin.video.example/?action=listing&category=Animals
        url = '{0}?action=listing&category={1}'.format(_url, category.channelName)
        # is_folder = True means that this item opens a sub-list of lower level items.
        is_folder = True
        # Add our item to the listing as a 3-element tuple.
        listing.append((url, list_item, is_folder))
    
    # Let python do the heay lifting of sorting our listing
    listing = sorted(listing, key=lambda item: item[1].getLabel())

    # Add our listing to Kodi.
    # Large lists and/or slower systems benefit from adding all items at once via addDirectoryItems
    # instead of adding one by ove via addDirectoryItem.
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    # Add a sort method for the virtual folder items (alphabetically, ignore articles)
    xbmcplugin.addSortMethod(_handle, xbmcplugin.SORT_METHOD_UNSORTED)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(_handle)

def listVideosPlaylist(playlistId, pageNumber = None):
    if pageNumber is None:
        pageNumber = 1

    listing = []
    videos = VideoLink.getVideosByPlaylist(playlistId, pageNumber-1)
    drawVideosListing(videos, [], pageNumber, playlistPageLength)

def listVideos(categoryName, pageNumber = None):
    """
    Create the list of playable videos in the Kodi interface.
    :param category: str
    :return: None
    """
    if pageNumber is None:
        pageNumber = 1
    # Get the list of videos in the category.
    category = Channel(categoryName, pageNumber)
    category.setPage(pageNumber)
    category.setThumbnail()
    videos = category.videos
    # Create a list for our items.
    drawVideosListing(videos, [category], pageNumber, 10)

def channelThumbnailFromChannels(name, channels):
    for channel in channels:
        if channel.channelName == name:
            return channel.thumbnail
    return ""

def listSubscriptionVideos(pageNumber):
    if pageNumber is None:
        pageNumber = 1
    # find all the channels we are subscribed to and set their thumbnails
    channels = []
    subs = fetchLoggedIn(baseUrl + "/subscriptions")
    subsSoup = BeautifulSoup(subs.text, 'html.parser')
    for sub in subsSoup.find_all('div', "subscription-container"):
        channelName = sub.find_all('a')[0].get('href').split('/')[-1]
        thumb = sub.find_all('img', 'subscription-image')[0].get('data-src').replace("_small.", "_large.")
        channels.append(Channel(channelName))
        channels[-1].thumbnail = thumb
    
    # fetch the actualsubscription videos
    subscriptionActivity = postLoggedIn(baseUrl + "/extend/", baseUrl,{"name": "subscribed", "index": (pageNumber - 1)})
    data = json.loads(subscriptionActivity.text)
    soup = BeautifulSoup(data['html'], 'html.parser')
    videos = []
    for videoContainer in soup.findAll('div', "video-card"):
        videos.append(VideoLink.getVideoFromVideoCard(videoContainer))
    
    drawVideosListing(videos, channels, pageNumber, playlistPageLength)

def drawVideosListing(videos, channels = [], pageNumber = 1, itemsPerPage = 10):
    listing = []
    for video in videos:
        list_item = xbmcgui.ListItem(label=video.title, thumbnailImage=video.thumbnail)
        list_item.setProperty('fanart_image', channelThumbnailFromChannels(video.channelName, channels))
        list_item.setInfo('video', {'title': video.title, 'genre': video.title})
        list_item.setArt({'landscape': video.thumbnail})
        list_item.setProperty('IsPlayable', 'true')
        url = '{0}?action=play&videoId={1}'.format(_url, video.id)
        contextOptions = [("Seed After Watching","PlayMedia("+url+"&seed=1)")]
        if hasSavePath():
            contextOptions.append(("Save and Watch Video","xbmc.PlayMedia("+url+"&save=1)"))
            contextOptions.reverse()
        list_item.addContextMenuItems(contextOptions)
        is_folder = False
        # Add our item to the listing as a 3-element tuple.
        listing.append((url, list_item, is_folder))
    # Add an entry to get the next page of results.
    if len(videos) >= itemsPerPage:
        list_item = xbmcgui.ListItem(label="Next Page...")
        url = '{0}?action=subscriptionActivity&page={1}'.format(_url, pageNumber + 1)
        listing.append((url, list_item, True))

    # Add our listing to Kodi.
    # Large lists and/or slower systems benefit from adding all items at once via addDirectoryItems
    # instead of adding one by ove via addDirectoryItem.
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    # Add a sort method for the virtual folder items (alphabetically, ignore articles)
    xbmcplugin.addSortMethod(_handle, xbmcplugin.SORT_METHOD_UNSORTED)
    # Finish creating a virtual folder.
    xbmcplugin.endOfDirectory(_handle)

def hasSavePath():
    save_path = xbmcplugin.getSetting(_handle, 'save_path')
    if len(save_path) > 0:
        return True
    return False

def playVideo(videoId, save = False, seed = False):
    print(videoId)
    videoUrl = VideoLink.getUrl(videoId)
    playing = 0
    # start webtorrent fetching path
    output = ""
    cnt = 0
    dlnaUrl = None
    save_path=""
    if save:
        try:
            save_path = xbmcplugin.getSetting(_handle, 'save_path')
        except:
            pass
        if len(save_path)>0:
            xbmc.log("saving to: "+save_path,xbmc.LOGERROR)
            # it's a bit of hack but setting a unique-ish filename prevents stalling when trying to verify previously fetched data.
            ts = time.time()
            save_path= " --out \"" + save_path + str(int(ts))
        else:
            xbmc.log("not saving ",xbmc.LOGERROR)

    command = 'webtorrent-hybrid download "' +  videoUrl + '" --dlna'+save_path
    xbmc.log("Executing: " + command ,xbmc.LOGERROR)

    webTorrentClient = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    xbmc.log("webtorrent-hybrid running with PID " + str(webTorrentClient.pid), xbmc.LOGNOTICE)
    for stdout_line in webTorrentClient.stdout:
        output += stdout_line.decode()
        cnt += 1
        if cnt > 10:
            break
    
    dlnaMatches = re.search('http:\/\/((\w|\d)+(\.)*)+:\d+\/\d+', output)
    if dlnaMatches:
        dlnaUrl = dlnaMatches.group()
    else:
        webTorrentClient.terminate()
        xbmc.log("could not determine the dlna URL.", xbmc.LOGERROR)
        raise ValueError("could not determine the dlna URL.")

    print("Streaming at: " + dlnaUrl)
    xbmc.log("seed_after="+str(seed), xbmc.LOGERROR)

    while webTorrentClient.poll() == None:
        if playing == 0:
            playing = 1
            playWithCustomPlayer(dlnaUrl, webTorrentClient,videoUrl,seed)

def playWithCustomPlayer(url, webTorrentClient,videoUrl="",seed_after=False):
    play_item = xbmcgui.ListItem(path=url)
    # Get an instance of xbmc.Player to work with.
    player = MyPlayer()

    # Allow retries if we haven't buffered enough video, yet.
    retries = 5
    attemptCount = 0

    while attemptCount < retries:
        attemptCount + 1
        try:
            player.play( url, play_item )
            xbmcplugin.setResolvedUrl(_handle, True, listitem=play_item)
            attemptCount = retries
        except:
            xbmc.log("Need to retry",xbmc.LOGERROR)
            time.sleep(10)
    
    while player.is_active:
        player.sleep(100)

    if seed_after == False:
        webTorrentClient.terminate()
        xbmc.log("No longer seeding",xbmc.LOGERROR)
    else:
        xbmc.log("Continuing to seed after playback.",xbmc.LOGERROR)



def router(paramstring):
    """
    Router function that calls other functions
    depending on the provided paramstring
    :param paramstring:
    :return:
    """
    # Parse a URL-encoded paramstring to the dictionary of
    # {<parameter>: <value>} elements
    params = dict(parse_qsl(paramstring))
    # Check the parameters passed to the plugin
    if params:
        if params['action'] == 'listing':
            # Display the list of videos in a provided category.
            listVideos(params['category'], int(params.get('page', '1')))
        elif params['action'] == 'subscriptionActivity':
            # Display the list of videos from /extend subscriptions
            listSubscriptionVideos(int(params.get('page', '1')))
        elif params['action'] == 'play':
            # Play a video from a provided URL.
            playVideo(params['videoId'], bool(params.get('save', False)), False)
        elif params['action'] == 'playlists':
            listPlaylists()
        elif params['action'] == 'playlist':
            listVideosPlaylist(params['playlistId'], int(params.get('page', '1')))
        elif params['action'] == 'subscriptions':
            listCategories()
    else:
        # If the plugin is called from Kodi UI without any parameters,
        # display the list of video categories
        #listCategories()
        defaultMenu()


if __name__ == '__main__':
    # Call the router function and pass the plugin call parameters to it.
    # We use string slicing to trim the leading '?' from the plugin call paramstring
    router(sys.argv[2][1:])
