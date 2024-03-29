import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
pd.set_option("display.max_rows", None)
import requests

client_id = ""
client_secret = ""
redirect = "http://www.google.com/"
username = ""
ptName = ""
playlist = ""


class spotifyAIRecommender:
    def __init__(self,username,redirect,client_secret,client_id):
        """
        Username - spotify username string
        Redict - your redirect URI string
        Scope - Your SCOPE string
        Client Secret- Your Client Secret
        Client ID - Your Client ID
        """
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(username=username,redirect_uri=redirect,scope= "playlist-modify-public"
, client_secret=client_secret, client_id = client_id))
        self.username = username
        self.redirect = redirect
        self.scope = "user-library-read"
        self.client_secret = client_secret
        self.client_id = client_id
    def features_from_playlist(self, playlist):
        """
        args:
        string - unique spotify playlist uri, can be out of scope
        returns:
        pandas dataframe - features of every song in playlist of len<100
        """
        print("Getting features from your playlist..")
        tracks = self.sp.playlist_tracks(playlist)
        song_list = []
        start_time = time.time()
        for song in tracks['items']:
            try:
                row_dict = self.sp.audio_features(song['track']['id'])[0]
                song_list.append(row_dict)
            except:
                print("exception error")
        df = pd.DataFrame(song_list)
        print(str(time.time()-start_time) + ' seconds..')
        return df
    def features_from_tracks(self, tracks):
        """
        args:
        string - list of format only uris, length must be <100
        returns:
        pandas dataframe - features of every song in playlist of len<100
        
        """
        print("Getting features from track list...")
        try:
            track_dict = self.sp.audio_features(tracks)
        except:
            print('Try Again')

        return pd.DataFrame(track_dict)
    
    def get_recs(self, dtype= 'track' , iterable = None):
        """
        args:
        dtype: string of either 'artist' or 'track'
        iterable: list of tracks or artist unique spotify uris
        return: a list of tracks in format [uri]
        """
        print("Getting Recs...")
        start_time = time.time()
        recs_list = []
        count =0
        if dtype == 'track':
            for track in iterable:
                count += 1
                print(f'{round(count/len(iterable) *100,2)}% Complete')
                recs = self.sp.recommendations(seed_tracks= [track], limit=50)
                for rec in recs['tracks']:
                    rec_item =  rec['id']
                    recs_list.append(rec_item)
        elif dtype == 'artist':
            for artist in iterable:
                count += 1
                print(f'{round(count/len(iterable) *100,2)}% Complete')
                recs = self.sp.recommendations(seed_artists= [artist], limit=50)
                for rec in recs['tracks']:
                    rec_item =  rec['id']
                    recs_list.append(rec_item)

        print(str(time.time()-start_time) + ' seconds..')
        
        recs_list =[*set(recs_list)]
        for i, item in enumerate(recs_list):
            if item in iterable:
                del recs_list[i]

        return recs_list
        
    
    def recsFromRecs(self, recs_list):
        print("Getting recs from recs")
        tracks = []
        for rows in recs_list:
            tracks.append(rows)
        new_recs = self.get_recs(dtype = 'track', iterable = tracks)
        return [*set(new_recs + recs_list)]
    
    def create_playlist_from_playlist(self, playlist):
        start = time.time()
        print("Creating New Playlist from your playlist...")
        #dataframe of features
        df = self.features_from_playlist(playlist)
        #size of df- number of songs
        ogsize = len(df)
        print("1/4 Done")
        recs = self.get_recs(dtype = 'track', iterable =df['id'])
        #make batches from recs of size 100, lists in format [name,uri]
        recs = [rec for rec in recs]
        #now recs is a list of ids
        recs_batches_ids = self.make_batches(recs)
        print("2/4 Done")
        #for loop that runs features_from_tracks on every batch
        temp_df_list=[]
        total = len(recs_batches_ids)
        for i,item in enumerate(recs_batches_ids): #for every batch of size 100
            temp_df_list.append(self.features_from_tracks(item))
            print("{}% done".format((i/total)*100))
        print("100% Done")
        #merges all dataframes
        recs_features = pd.concat(temp_df_list)
        print("3/4 Done")
        recs_df_data = recs_features.iloc[:,0:11]
        df_data =df.iloc[:,0:11] #df of original playlist
        scaler = StandardScaler()
        X= scaler.fit_transform(df_data)
        km = KMeans(n_clusters = ogsize)
        km.fit(X)
        Xrecs = scaler.transform(recs_df_data)
        centers = km.transform(Xrecs)
        labels_ = km.predict(Xrecs)
        og_labels = km.predict(X)
        df['Labels'] = og_labels
        print("4/4 Done")
        recs_features['labels'] = labels_
        recs_features['distance']= np.absolute(centers).min(axis =1)
        print(f'{time.time()-start} seconds...')
        return recs_features, df, recs_df_data
    
    def filter_playlist(self,df,max_per_song):
        '''
        df of playlist with labels and distances
        max_per_song: integer of how many songs alike per song in og playlist
        '''
        playlist_df = df
        playlist_df = playlist_df.sort_values(by = ['distance'], axis =0, ascending=True)
        counter_dict = {}
        final_list = []
        for row in playlist_df.iterrows():
            if row[1]['labels'] not in counter_dict:
                counter_dict[row[1]['labels']] = 1
            else:
                counter_dict[row[1]['labels']] += 1
            

            if counter_dict[row[1]['labels']] <= max_per_song and row[1]['distance']>0.01:
                final_list.append(row[1])
        filtered = pd.DataFrame(final_list[:99])
        
        
        filtered['Reference URI'] = filtered['labels'].apply(self.get_reference)
        
        filtered_batches = []       # loop over the list    
        for i in range(0, len(filtered['Reference URI']), 50):      
            filtered_batches.append(list(filtered['Reference URI'])[i:i + 50])  
        
        ref_names= []
        for item in filtered_batches:
            ref_names.append([track['name'] for track in self.sp.tracks(item)['tracks']])
        
        
        ref_names= sum(ref_names, [])
        filtered['Reference Name'] = ref_names
        
        
        track_batches = []       # loop over the list    
        for i in range(0, len(filtered['uri']), 50):      
            track_batches.append(list(filtered['uri'])[i:i + 50])  
        
        track_names= []
        for item in track_batches:
            track_names.append([track['name'] for track in self.sp.tracks(item)['tracks']])
        
        track_names = sum(track_names, [])
        filtered['Track Name'] = track_names
        
        return filtered
        
        

    
    def createSpotifyPlaylist(self,playListName, tracks):
        """
        playListName - name of playlist
        username - username
        tracks - list of track IDs
        """
        playlist_info = self.sp.user_playlist_create(username, playListName, public=True, collaborative=False, description='This playlist was made by AI')
        self.sp.user_playlist_add_tracks(username, playlist_info['id'], tracks, position=None)
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(username=self.username,redirect_uri=self.redirect,scope= "user-library-read"
    , client_secret=self.client_secret, client_id = self.client_id))
        
    def make_batches(self,_list):  
        """
        args: _list is a list
        return: makes a list of batches of len:100
        """
        batch_list = []       # loop over the list    
        for i in range(0, len(_list), 100):      
            batch_list.append(_list[i:i + 100])       
            # return the list of batches    
        return batch_list     
    def merge_lists(self,list_of_lists): 
        """
        args: list_lists: takes list of lists of any size
        returns: merged list of all elements - as a set where every element is unique
        """
        
        merged_list = []    
        for list_ in list_of_lists:     
            for element in list_:        
                if element not in merged_list:          
                    merged_list.append(element)     
        return merged_list  
    
    def get_reference(self, label):
        for row in og_df.iterrows():
            if (label == row[1]['Labels']):
                return row[1]['uri']
    def get_name(self, uri):
        return(self.sp.track(uri)['name'])
    
if __name__ == "__main__":
    recommender = spotifyAIRecommender(username, redirect, client_secret,client_id)
    playlist_df, og_df, ogcenters = recommender.create_playlist_from_playlist(playlist)
    filtered = recommender.filter_playlist(playlist_df,5)
    recommender.createSpotifyPlaylist(ptName, list(filtered['id']))






        
    
    
        
