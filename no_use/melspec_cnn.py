import librosa
import librosa.display
# import IPython.display as ipd
import numpy as np
import pickle
import matplotlib.pyplot as plt
from os.path import *
import os
from sklearn.model_selection import train_test_split
from tqdm import tqdm # show status bar of for

import keras
from keras.models import Sequential
from keras.layers import Dense, Dropout, Flatten, Conv2D, MaxPooling2D
from keras.callbacks import ModelCheckpoint, EarlyStopping #, LambdaCallback
from keras.utils import to_categorical
from keras import optimizers


WAV_PATH = './sunjong/wav820/'
SAMPLING_RATE = 44100
MFCC_NUM = 128 # n_mels for spectogram
MFCC_MAX_LEN = 2000


MODEL_SAVE_FOLDER_PATH = '../../../../data/models/'

if not os.path.exists(MODEL_SAVE_FOLDER_PATH):
  os.mkdir(MODEL_SAVE_FOLDER_PATH)

model_path = MODEL_SAVE_FOLDER_PATH + 'melfreq-' + '{epoch:02d}-{val_loss:.4f}.hdf5'

# Save the model after every epoch
cb_checkpoint = ModelCheckpoint(filepath=model_path, monitor='val_loss',
								verbose=1, save_best_only=True)

# Stop training when performance goes down
# cb_early_stopping = EarlyStopping(monitor='val_loss', patience=10)


def wav2mfcc(wave, max_len=MFCC_MAX_LEN):
	# mfcc = librosa.feature.mfcc(wave, n_mfcc=MFCC_NUM, sr=SAMPLING_RATE)
	mfcc = librosa.feature.mfcc(wave, n_mfcc=MFCC_NUM, sr=SAMPLING_RATE)
	print(mfcc.shape)

	# if max length exceeds mfcc lengths then pad the remaining ones
	if (max_len > mfcc.shape[1]):
		pad_width = max_len - mfcc.shape[1]
		# mode=constant : init by 0
		# ((0,0), (0,pad_width)) -> 0 row 0 , 0 column pad_width : only add to column
		mfcc = np.pad(mfcc, pad_width = ((0,0), (0,pad_width)), mode='constant')

	# else cutoff the remaining parts
	else:
		mfcc = mfcc[:,:max_len]

	return mfcc

def wav2melspec(wave, max_len=MFCC_MAX_LEN):
	
	melspec = librosa.feature.melspectrogram(y=wave, n_fft=1024, hop_length=256, sr=SAMPLING_RATE, n_mels=MFCC_NUM)

	# if max length exceeds mfcc lengths then pad the remaining ones
	if (max_len > melspec.shape[1]):
		pad_width = max_len - melspec.shape[1]
		# mode=constant : init by 0
		# ((0,0), (0,pad_width)) -> 0 row 0 , 0 column pad_width : only add to column
		melspec = np.pad(melspec, pad_width = ((0,0), (0,pad_width)), mode='constant')

	# else cutoff the remaining parts
	else:
		melspec = melspec[:,:max_len]

	return melspec


# Make Dataset
X, y = [], []
def datasetXy(label, wave):
	y.append(label)
	melspec = wav2melspec(wave) # (20, 2000)
	melspec = melspec.tolist()
	X.append(melspec) # append list to list
	# print(melspec.shape)


files = []
genres = ['Classical', 'Jazz', 'Pop', 'Rock', 'Country']
genre_num = 0
for genre in genres:
	dir_genre = WAV_PATH + genre
	for f in os.listdir(dir_genre):
		if isfile(join(dir_genre, f)) :
			new_path = dir_genre + '/' + f
			files.append((new_path, genre_num))

	genre_num += 1

# mode
mode = 'save'

if mode == 'save':
	for file in tqdm(files):
		wave, sr = librosa.load(file[0], sr=SAMPLING_RATE, mono=True, duration=20.0)
		# wave = wave[::3] # audio downsampling
		datasetXy(file[1], wave)

	X = np.stack(X, axis=0) # vertical stack
	y = np.array(y)
	print("X shape is:", X.shape)
	print("y shape is:", y.shape)
	# with open('../../../../data/mymelspec_X.pkl', 'wb') as f:
	# 	pickle.dump(X, f)
	# with open ('../../../../data/mymelspec_y.pkl', 'wb') as t:
	# 	pickle.dump(y, t)
	print("save success...")


elif mode == 'load':
	with open('../../../../data/mymelspec_X.pkl', 'rb') as f:
		X = pickle.load(f)
		print(X.shape)
	with open ('../../../../data/mymelspec_y.pkl', 'rb') as t:
		y = pickle.load(t)
	print("load success...")


y_hot = to_categorical(y) # not train label 5, but train [0,0,0,0,1] (prob of label 5 to 1)

X_train, X_test, y_train, y_test = train_test_split(X, y_hot, test_size=0.2, random_state=True, shuffle=True)
# print(X_train.shape)

# Feature dimension & other options
feature_dim_1 = MFCC_NUM # 128
feature_dim_2 = MFCC_MAX_LEN # 1000
channel = 1 # each pixel has only db . ex) if each has RGB, channel = 3
epochs = 20
batch_size = 80
verbose = 1
num_classes = 5

# Reshaping dataset to perform 2D conv (tot data, dim1, dim2, channel)
X_train = X_train.reshape(X_train.shape[0], feature_dim_1, feature_dim_2, channel)
X_test = X_test.reshape(X_test.shape[0], feature_dim_1, feature_dim_2, channel)

y_train_hot = y_train
y_test_hot = y_test

def Model():
	# with uncomment -> AlexNet
	# some paper said, simple model is better because of overfitting

	model = Sequential()
	model.add(Conv2D(16, kernel_size=(3, 3), strides=(1,1), padding='same', activation='relu', 
		input_shape=(feature_dim_1, feature_dim_2, channel)))
	model.add(MaxPooling2D(pool_size=(2, 2), strides=(2,2)))
	model.add(Dropout(0.25))

	model.add(Conv2D(32, kernel_size=(3, 3), strides=(1,1), padding='same', activation='relu', 
		input_shape=(feature_dim_1, feature_dim_2, channel)))
	model.add(MaxPooling2D(pool_size=(2, 2), strides=(2,2)))
	model.add(Dropout(0.25))

	model.add(Conv2D(64, kernel_size=(3, 3), strides=(1,1), padding='same', activation='relu', 
		input_shape=(feature_dim_1, feature_dim_2, channel)))
	model.add(MaxPooling2D(pool_size=(2, 2), strides=(2,2)))
	model.add(Dropout(0.25))

	# model.add(Conv2D(128, kernel_size=(3, 3), strides=(1,1), padding='same', activation='relu', 
	# 	input_shape=(feature_dim_1, feature_dim_2, channel)))
	# model.add(MaxPooling2D(pool_size=(2, 2), strides=(2,2)))
	# model.add(Dropout(0.25))

	# model.add(Conv2D(256, kernel_size=(3, 3), strides=(1,1), padding='same', activation='relu', 
	# 	input_shape=(feature_dim_1, feature_dim_2, channel)))
	# model.add(MaxPooling2D(pool_size=(2, 2), strides=(2,2)))
	# model.add(Dropout(0.25))

	model.add(Flatten())
	model.add(Dropout(0.5))

	model.add(Dense(512, activation='relu', kernel_regularizer=keras.regularizers.l2(0.02)))
	model.add(Dropout(0.25))
	model.add(Dense(256, activation='relu', kernel_regularizer=keras.regularizers.l2(0.02)))
	model.add(Dropout(0.25))
	model.add(Dense(128, activation='relu', kernel_regularizer=keras.regularizers.l2(0.02)))
	model.add(Dropout(0.25))
	model.add(Dense(num_classes, activation='softmax', kernel_regularizer=keras.regularizers.l2(0.02)))
	
	return model


model = Model()
model.summary()

optimizer = optimizers.Adam(lr=0.001)
# optimizer = optimizers.RMSprop(lr=0.001)

# metrics: List of metrics to be evaluated by the model during training and testing
model.compile(loss=keras.losses.categorical_crossentropy,
				optimizer=optimizer, metrics=['accuracy']) 
# train & test
history = model.fit(X_train, y_train_hot, batch_size=batch_size, epochs=epochs,
			verbose=verbose, validation_data=(X_test, y_test_hot), callbacks=[cb_checkpoint]) # callbacks added except cb_early_stopping


# visualizing
print(history.history.keys())

# Summarize history for accuracy
plt.plot(history.history['accuracy'])
plt.plot(history.history['val_accuracy'])
plt.title('model accuracy')
plt.ylabel('accuracy')
plt.xlabel('epoch')
plt.legend(['train', 'test'], loc='upper left')
# plt.show()
plt.savefig('CNN_acc.png', dpi=300)

# Summarize history for loss
plt.plot(history.history['loss'])
plt.plot(history.history['val_loss'])
plt.title('model loss')
plt.ylabel('loss')
plt.xlabel('epoch')
plt.legend(['train', 'test'], loc='upper left')
# plt.show()
plt.savefig('CNN_loss.png', dpi=300)


# -----------------------------test----------------------------------------
# wave, sr = librosa.load(TEST_WAV_PATH, mono=True, sr=None)
# mfcc = wav2mfcc(wave)
# X_test = mfcc.reshape(1, feature_dim_1, feature_dim_2, channel)
# preds = model.predict(X_test)[0]