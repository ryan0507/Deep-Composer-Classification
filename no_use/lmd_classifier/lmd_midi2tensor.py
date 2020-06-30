import numpy as np
import pandas as pd
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
import pretty_midi
import warnings
import os

from scipy.io.wavfile import write
import py_midicsv
import torch.nn as nn
import torchaudio
import torch
import sys


#print(data_middle)
#print(data_note_on)
#print(data_note_off)

#set midi to frequency convert table
#It can transform midi notes to frequency
midi_freq = {127:13289.75, 126:12543.85, 125:11175.30, 124:10548.08,
			 123:9956.06, 122:9397.27, 121:8869.84, 120:8372.02, 119:7902.13,
			 118:7458.62, 117:7040.00, 116:6644.88, 115:6271.93, 114:5919.91,
			 113:5587.65, 112:5274.04, 111:4978.03, 110:4698.64, 109:4434.92,
			 108:4186.01, 107:3951.07, 106:3729.31, 105:3520.00, 104:3322.44,
			 103:3135.96, 102:2959.96, 101:2793.83, 100:2637.02, 99:2489.02,
			 98:2349.32, 97:2217.46, 96:2093.00, 95:1975.53, 94:1864.66,
			 93:1760.00, 92:1661.22, 91:1567.98, 90:1479.98, 89:1396.91,
			 88:1318.51, 87:1244.51, 86:1174.66, 85:1108.73, 84:1046.50,
			 83:987.77, 82:932.33, 81:880.00, 80:830.61, 79:783.99, 78:739.99,
			 77:698.46, 76:659.26, 75:622.25, 74:587.33, 73:554.37, 72:523.25,
			 71:493.88, 70:466.16, 69:440.00, 68:415.30, 67:392.00, 66:369.99,
			 65:349.23, 64:329.63, 63:311.13, 62:293.66, 61:277.18, 60:261.63,
			 59:246.94, 58:233.08, 57:220.00, 56:207.65, 55:196.00, 54:185.00,
			 53:174.61, 52:164.81, 51:155.56, 50:146.83, 49:138.59, 48:130.81,
			 47:123.47, 46:116.54, 45:110.00, 44:103.83, 43:98.00, 42:92.50,
			 41:87.31, 40:82.41, 39:77.78, 38:73.42, 37:69.30, 36:65.41,
			 35:61.74, 34:58.27, 33:55.00, 32:51.91, 31:49.00, 30:46.25,
			 29:43.65, 28:41.20, 27:38.89, 26:36.71, 25:34.65, 24:32.70,
			 23:30.87, 22:29.14, 21:27.50, 20:25.96, 19:24.50, 18:23.12,
			 17:21.83, 16:20.60, 15:19.45, 14:18.35, 13:17.32, 12:16.35,
			 11:15.43, 10:14.57, 9:13.75, 8:12.98, 7:12.25, 6:11.56,
			 5:10.91, 4:10.30, 3:9.72, 2:9.18, 1:8.66, 0:8.18}


#sampling rate
sr = 10000.0
Ts = 1/sr



def sound_wave (midi_note, start_time, duration,padding_size,sampling_rate = 10000.0):
	# midi_to_freq: input: midi note (int) , output: frequency (int) by dictionary
	# start_time: use for phase difference
	# duration: length of list
	#padding_size: We need to padding the data 804440
	#Sampling_rate = 10000.0

	global Ts
	t = np.arange(start_time,start_time + duration,Ts)
	sine_wave = np.sin(midi_freq[midi_note] * 2 * np.pi *t + 0)
	#print("Sine Wave shape :", sine_wave.shape[0])
	#print("Check ")

	# For example if Duration = 1 , start_time = 3, [3,4)arange array make, Padding Size = 7
	# 0 1 2 3 4 5 6 (index)   we need to pad 0 left 3 value and pad 3 values for right
	# print("start: ",int(start_time * 10000))
	# print("end: ",int(padding_size - (duration+start_time)*10000))
	if(start_time*10000 <= padding_size):
		pad_sine_wave = np.pad(sine_wave,(int(start_time * 10000), int(padding_size - (duration+start_time)*10000)),'constant',constant_values=0.0)
	else:
		# print('Error: Negative Value')
		pad_sine_wave=np.zeros((padding_size,))
	# print(pad_sine_wave.shape)
	if (pad_sine_wave.shape[0] < padding_size):
		pad_sine_wave= np.pad(pad_sine_wave,(int(padding_size - pad_sine_wave.shape[0]),0),'constant',constant_values = 0.0)
	elif (pad_sine_wave.shape[0] > padding_size):
	   pad_sine_wave = pad_sine_wave[int(pad_sine_wave.shape[0] - padding_size):]
	# print(pad_sine_wave.shape)
	return pad_sine_wave



def get_genres(path):
	"""
	This function reads the genre labels and puts it into a pandas DataFrame.
	
	@input path: The path to the genre label file.
	@type path: String
	
	@return: A pandas dataframe containing the genres and midi IDs.
	@rtype: pandas.DataFrame
	"""
	ids = []
	genres = []
	with open(path) as f:
		line = f.readline()
		while line:
			if line[0] != '#':
				[x, y, *_] = line.strip().split("\t")
				ids.append(x)
				genres.append(y)
			line = f.readline()
	genre_df = pd.DataFrame(data={"Genre": genres, "TrackID": ids})
	return genre_df

# Get the Genre DataFrame
genre_path = "../../../../data/lmd/msd_tagtraum_cd1.cls"
genre_df = get_genres(genre_path)

# Create Genre List and Dictionary
label_list = list(set(genre_df.Genre))
label_dict = {lbl: label_list.index(lbl) for lbl in label_list}

# Print to Visualize
# print(genre_df.head(), end="\n\n")
# print(label_list, end="\n\n")
# print(label_dict, end="\n\n")

def get_matched_midi(midi_folder, genre_df):
	"""
	This function loads in midi file paths that are found in the given folder, puts this data into a
	pandas DataFrame, then matches each entry with a genre described in get_genres.
	
	@input midi_folder: The path to the midi files.
	@type midi_folder: String
	@input genre_df: The genre label dataframe generated by get_genres.
	@type genre_df: pandas.DataFrame
	
	@return: A dataframe of track id and path to a midi file with that track id.
	@rtype: pandas.DataFrame
	"""
	# Get All Midi Files
	track_ids, file_paths = [], []
	for dir_name, subdir_list, file_list in os.walk(midi_folder):
		if len(dir_name) == (36+21):
			track_id = dir_name[(18+21):]
			file_path_list = ["/".join([dir_name, file]) for file in file_list]
			for file_path in file_path_list:
				track_ids.append(track_id)
				file_paths.append(file_path)
	all_midi_df = pd.DataFrame({"TrackID": track_ids, "Path": file_paths})
	
	# Inner Join with Genre Dataframe
	df = pd.merge(all_midi_df, genre_df, on='TrackID', how='inner')
	return df.drop(["TrackID"], axis=1)

# Obtain DataFrame with Matched Genres to File Paths
midi_path = "../../../../data/lmd/lmd_matched"
matched_midi_df = get_matched_midi(midi_path, genre_df)

# Print to Check Correctness
# print(matched_midi_df.head())



# def normalize_features(features):
# 	"""
# 	This function normalizes the features to the range [-1, 1]
	
# 	@input features: The array of features.
# 	@type features: List of float
	
# 	@return: Normalized features.
# 	@rtype: List of float
# 	"""
# 	tempo = (features[0] - 150) / 300
# 	num_sig_changes = (features[1] - 2) / 10
# 	resolution = (features[2] - 260) / 400
# 	time_sig_1 = (features[3] - 3) / 8
# 	time_sig_2 = (features[4] - 3) / 8
# 	return [tempo, resolution, time_sig_1, time_sig_2]

# # original features
# # def get_features(path):
# #     """
# #     This function extracts the features from a midi file when given its path.
	
# #     @input path: The path to the midi file.
# #     @type path: String
	
# #     @return: The extracted features.
# #     @rtype: List of float
# #     """
# #     try:
# #         # Test for Corrupted Midi Files
# #         with warnings.catch_warnings():
# #             warnings.simplefilter("error")
# #             file = pretty_midi.PrettyMIDI(path)
			
# #             tempo = file.estimate_tempo()
# #             num_sig_changes = len(file.time_signature_changes)
# #             resolution = file.resolution
# #             ts_changes = file.time_signature_changes
# #             ts_1 = 4
# #             ts_2 = 4
# #             if len(ts_changes) > 0:
# #                 ts_1 = ts_changes[0].numerator
# #                 ts_2 = ts_changes[0].denominator
# #             return normalize_features([tempo, num_sig_changes, resolution, ts_1, ts_2])
# #     except:
# #         return None

CSV_PATH = './../../../../data/lmd/csv/'
SAVE_PATH = './../../../../data/tensors/'
GENRES = ['Jazz', 'Folk', 'Electronic', 'Latin', 'Vocal', 'Blues', 'Rap', 'International', 'RnB', 'Reggae', 'New_Age', 'Pop_Rock', 'Country']

def get_features(path, genre_index):
		
	try:
		csv_string = py_midicsv.midi_to_csv(path)  #Set to File Directory Here!
		## Caution: csv_string is List[string]  : we need to manipulate this data preprocess
		## Split all of the string elements to list elements

		tmp_list = []
		for i in range(0,len(csv_string)):
			temp=np.array(csv_string[i].replace("\n","").replace(" ","").split(","))
			tmp_list.append(temp)

		data = pd.DataFrame(tmp_list)
		mid_name = path.split('/')[11]
		data.to_csv(CSV_PATH + GENRES[genre_index] + '/' + mid_name +'.csv' ,header=False, index = False)

		# Manipulating Dataframe
		# Drop all of the other colunms

		#BitMask for inside the dataframe, DF
		#Define to cut midi files --> Too Long and it makes overflow

		MAX_DF = 500

		data_note = data [ (data[2]== 'Note_on_c') | (data[2]=='Note_off_c')]
		# print(data_note)

		#Manipulate data_note_on DF
		data_note_on = data[(data[2] == 'Note_on_c') & (data[5]!='0')]

		#Change the MAX_DF
		if data_note_on.shape[0] > 500:
			MAX_DF = 500
		else:
			MAX_DF = data_note_on.shape[0]

		data_note_on= data_note_on.loc[:,0:5]
		data_note_on.reset_index(drop=True)
		data_note_on.columns = ['Track','Time','Event_Type','Channel','Note','Velocity']
		data_note_on.index = range(0,data_note_on.shape[0])
		data_note_on.drop(data_note_on.index[MAX_DF:],inplace = True)
		#Manipulate data_note_off DF
		data_note_off = data[(data[2] == 'Note_off_c') | ((data[2]=='Note_on_c') & (data[5] == '0'))]
		data_note_off= data_note_off.loc[:,0:5]
		data_note_off.reset_index(drop=True)
		data_note_off.columns = ['Track','Time','Event_Type','Channel','Note','Velocity']
		data_note_off.index = range(0,data_note_off.shape[0])

		#Cheking
		# print(data_note_on)
		# print(data_note_off)

		# Make the new DataFrame for Middle State
		# Cut the shape of DataFrame
		data_middle = pd.DataFrame(index = range(0,MAX_DF),
							   columns= ['Track','Duration','Event_Type','Channel','Note','Velocity'])

		# Shape returns tuple
		# print(data_middle)
		# print(data_note_on)

		#Calculate duration
		for i in range(0,MAX_DF):
			for j in range(0,data_note_off.shape[0]):
				if ((data_note_on.iloc[i])['Note'] == (data_note_off.iloc[j])['Note'] and (data_note_on.iloc[i])['Track'] == (data_note_off.iloc[j])['Track'] ):
					data_middle.iloc[i] = data_note_on.iloc[i]
					(data_middle.iloc[i])['Duration'] = int((data_note_off.iloc[j])['Time']) - int((data_note_on.iloc[i])['Time'])
					data_note_off = data_note_off.drop(index = j)
					data_note_off.index = range(0, data_note_off.shape[0])
					break
				else:
					continue

		#Initialize Data to List
		t_start_list = []
		t_duration = []
		note = []
		for i in range (0,MAX_DF):
			t_start_list.append(int(data_note_on.iloc[i,1])/1000)
			t_duration.append(int(data_middle.iloc[i,1])/1000)
			note.append(int(data_note_on.iloc[i,4]))


		total_t = np.arange(0, t_start_list[MAX_DF-1]+t_duration[MAX_DF-1],1/sr)
		PADDING_SIZE = total_t.shape[0]

		#SET THE BASE WAVE TO ADD UP
		base_sine_wave = np.sin(0 * 2 * np.pi * total_t + 0)
		abs_sum_wave = 0
		sum_wave = 0

		for i in range(0,MAX_DF):
			abs_sum_wave = abs_sum_wave + np.abs(sound_wave(midi_note= note[i],start_time = t_start_list[i],duration = t_duration[i],padding_size= PADDING_SIZE))
			sum_wave = sum_wave + sound_wave(midi_note= note[i],start_time = t_start_list[i],duration = t_duration[i],padding_size= PADDING_SIZE)



		### We should focus on scaled
		scaled = np.int16((sum_wave / np.max(abs_sum_wave)) * 32767)
		temp = scaled.shape[0]
		# print(temp)

		#Change the scaled for tensor
		tensor_format = scaled.reshape((1,temp))
		tensor_format = torch.from_numpy(tensor_format)
		# print(tensor_format)


		# append tensor to tensor_list
		print("tensor shape: ", tensor_format.shape)
		print('--------------------------------------------------------')
		# tensor_list.append(tensor_format)

		return tensor_format

# with open(SAVE_PATH + "Tensor_Data_"+ str(GENRES[genre_index]) +".txt","a") as f:
# 	f.write('current: file :' + file_name[cur_file] + "< " + GENRES[genre_index] + ">" + "\n")
# 	f.write(str(temp))
# 	f.write("\n")

# write('/nfs/home/ryan0507/pycharm_maincomputer/wav/'+GENRES[genre_index] + '/' + file_name[cur_file] + '.wav', 10000, scaled)



	except:
		# with open("./error_log/Error_Record_"+ str(GENRES[genre_index]) +".txt", "a") as f:
		# 	f.write("Error Occured With: " + file_name[cur_file] + "\n")
		# 	f.write(str(sys.exc_info()[0]))
		# print("Error on file: ", path)
		# print('--------------------------------------------------------')

		# os.remove(path)
		# pass

		return None


tot_tensor_list = [[] for i in range(len(GENRES))]
# each are ['Jazz', 'Folk', 'Electronic', 'Latin', 'Vocal', 'Blues', 'Rap', 'International', 'RnB', 'Reggae', 'New_Age', 'Pop_Rock', 'Country']

# print(tot_tensor_list)
# Jazz_list, Folk_list, Electronic_list, Latin_list, Vocal_list,Blues_list, Rap_list = 
# International_list, RnB_list, Reggae_list, New_Age_list, Pop_Rock_list, Country_list = 

def extract_midi_features(path_df):
	"""
	This function takes in the path DataFrame, then for each midi file, it extracts certain
	features, maps the genre to a number and concatenates these to a large design matrix to return.
	
	@input path_df: A dataframe with paths to midi files, as well as their corresponding matched genre.
	@type path_df: pandas.DataFrame
	
	@return: A matrix of features along with label.
	@rtype: numpy.ndarray of float
	"""
	all_features = []
	for index, row in path_df.iterrows():
		print('current file:', row.Path)
		genre = label_dict[row.Genre]
		if len(tot_tensor_list[0]) == 100 and len(tot_tensor_list[1]) == 100 and len(tot_tensor_list[2]) == 100 and len(tot_tensor_list[3]) == 100 and len(tot_tensor_list[4]) == 100 and len(tot_tensor_list[5]) == 100 and len(tot_tensor_list[6]) == 100 and len(tot_tensor_list[7]) == 100 and len(tot_tensor_list[8]) == 100 and len(tot_tensor_list[9]) == 100 and len(tot_tensor_list[10]) == 100 and len(tot_tensor_list[11]) == 100 and len(tot_tensor_list[12]) == 100: break
		if len(tot_tensor_list[genre]) == 100: continue

		features = get_features(row.Path, genre) # midi tensor
		if features is not None:
			print(features.shape)
			tot_tensor_list[genre].append(features)
	# return np.array(all_features) # tensor list

extract_midi_features(matched_midi_df)

# save tensor
for i in range(len(tot_tensor_list)):
	print(GENRES[i],' : ',len(tot_tensor_list[i]))
	torch.save(tot_tensor_list[i], './../../../../data/lmd/tensors/'+ GENRES[i] + '.pt')
	print(GENRES[i], ' saved!')

