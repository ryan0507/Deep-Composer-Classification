import os
import numpy as np
import torch
import librosa
import torchaudio
import pickle


from Fin_hparams import hparams


TENSOR_PATH = '/nfs/home/kssung/midiclass/new_midiset/tensors/' # absolute path
GENRES = ['Blues','HipHopRap','Jazz','NewAge','Pop']

# def load_list(list_name, hparams):
# 	with open(os.path.join(hparams.dataset_path, list_name)) as f:
# 		file_names = f.read().splitlines()
# 		return file_names

# original melspectogram
# def melspectrogram(file_name, hparams):
	
# 	####### original librosa version #######

# 	y, sr = librosa.load(os.path.join(hparams.dataset_path, file_name), hparams.sample_rate)
# 	wave_tensor = torch.tensor(y)
	
# 	'''
	
# 	# separate it to time windows, and apply the Fourier Transform on each time window
# 	S = librosa.stft(y, n_fft=hparams.fft_size, hop_length=hparams.hop_size, win_length=hparams.win_size)
# 	print(S.shape)
# 	# non linear transformation matrix
# 	# partitions the Hz scale into bins, and transforms each bin into a corresponding bin in the Mel Scale, using a overlapping triangular filters
# 	# low freq: high energy, high freq: low energy (not considerable)
# 	mel_basis = librosa.filters.mel(hparams.sample_rate, n_fft=hparams.fft_size, n_mels=hparams.num_mels)
# 	# the amplitude of one time window, compute the dot product with mel to perform the transformation
# 	mel_S = np.dot(mel_basis, np.abs(S))
# 	mel_S = np.log10(1+10*mel_S)
# 	mel_S = mel_S.T

# 	# print(mel_S.shape)

# 	'''

# 	####### torch audio version (MelSpectogram ver) #######
# 	# file already pickle of tensor
# 	# with open(os.path.join(hparams.dataset_path, file_name), 'rb') as f:
# 	# 	wav_tensor = pickle.load(f)
# 	mel_S = torchaudio.transforms.MelSpectrogram(sample_rate=hparams.sample_rate, n_fft=hparams.fft_size,
# 													win_length=hparams.win_size, hop_length=hparams.hop_size, n_mels=hparams.num_mels)(wave_tensor)

# 	mel_S = torch.log10(1+10*mel_S)

# 	####### torch audio version (stft * men_basis -> log -> transpose) #######
# 	# separate it to time windows, and apply the Fourier Transform on each time window
	
# 	# S = torch.stft(wave_tensor, n_fft=hparams.fft_size, hop_length=hparams.hop_size, win_length=hparams.win_size)
# 	# print(S.shape)
# 	# # non linear transformation matrix
# 	# # partitions the Hz scale into bins, and transforms each bin into a corresponding bin in the Mel Scale, using a overlapping triangular filters
# 	# # low freq: high energy, high freq: low energy (not considerable)
# 	# mel_basis = torchaudio.transforms.MelScale(n_mels=hparams.num_mels, sample_rate=hparams.sample_rate, n_stft=hparams.fft_size)
# 	# print(mel_basis.fb.shape)
# 	# # the amplitude of one time window, compute the dot product with mel to perform the transformation
# 	# mel_S = mel_basis(torch.abs(S))
# 	# mel_S = torch.log10(1+10*mel_S)
# 	# mel_S = torch.t(mel_S)



# 	print(mel_S.shape)

# 	return mel_S

# Function to get genre index for the give file
def get_label(file_name, hparams):
	genre = file_name.split('.')[0]
	label = hparams.genres.index(genre)
	return label


def tensor2mel(wave_tensor, hparams):

	# # MelSpectrogram
	mel_S = torchaudio.transforms.MelSpectrogram(sample_rate=hparams.sample_rate, n_fft=hparams.fft_size,
													win_length=hparams.win_size, hop_length=hparams.hop_size, n_mels=hparams.num_mels)(wave_tensor)

	mel_S = torch.log10(1+10*mel_S)

	# print(mel_S.shape)

	# MFCC
	# mel_S = torchaudio.transforms.MFCC(sample_rate=hparams.sample_rate, n_mfcc=40, log_mels=True)(wave_tensor)


	return mel_S


def resize_array(array, length):
	array_T = array.t() # transpose
	# print("transpose shape:",array_T.shape)
	resize_array = torch.zeros((length, array_T.shape[1]))
	if array_T.shape[0] >= length:
		resize_array = array_T[:length]
	else:
		resize_array[:array_T.shape[0]] = array_T

	return resize_array

	# resize_array = np.zeros((length, array.shape[1]))
	# if array.shape[0] >= length:
	# 	resize_array = array[:length]
	# else:-------
	# 	resize_array[:array.shape[0]] = array


	# return resize_array

def main():
	print("Extracting Feature")
	# list_names = ['train_list.txt', 'valid_list.txt', 'test_list.txt']
	err = 0
	tot_mel_num = [0,0,0,0,0]
	train_test_valnum = [0,0,0]
	# train: 250 * 5 genre -> 67%
	# valid: 60 * 5 genre -> 16%
	# test: 60 * 5 genre -> 16%
	for f in os.listdir(TENSOR_PATH):

		# if f == 'dataset': continue

		num = 0 # if num < 250: train, elif num < 310: test, elif num < 370: valid
		label = get_label(f, hparams)
		print('Label:', GENRES[label])

		file_path = TENSOR_PATH + f
		print(file_path)
		tensor_list = torch.load(file_path) # len: 300
		for i, tensor in enumerate(tensor_list):
			tensor_list[i] = tensor.float()

		print(len(tensor_list))
		# continue

		for k, wav_tensor in enumerate(tensor_list):
			
			# if num < 3150: # 4500 * 0.7
			# 	set_name = 'train'
			# elif num < 3825: # 4500 * 0.15
			# 	set_name = 'test'
			# elif num < 4500:
			# 	set_name = 'valid'
			# else: # only take 4500 for each genre
			# 	break

			feature = tensor2mel(wav_tensor, hparams) # [1,128, something]
			feature = feature.reshape(feature.shape[1], feature.shape[2]) # [128, something]
			print('feature size:',feature.shape)

			# if feature.shape[1] < 1024: continue

			# to check tot num for each genres of mel >= 1024
			# tot_mel_num[label] += 1


			# feature = resize_array(feature, hparams.feature_length)
			# print('after resize:', feature.shape) # (1024, 128)

			
			'''
			# Data Arguments
			num_chunks = feature.shape[0]//hparams.num_mels # 1024 / 128 = 8, 672 / 224 = 3
			# print(num_chunks)

			print('-------------------')

			# data_chuncks = np.split(feature, num_chunks)
			data_chuncks = torch.chunk(feature, num_chunks, dim=0) # (1024, 128) => 8 x (128,128) # not use torch.split !!!
			'''

			# for same chunk length
			print("###########################################################")
			data_chuncks = []
			num_chunks = feature.shape[1] // hparams.num_mels
			feature = feature.t()

			for i in range(num_chunks):
				data_chuncks.append(feature[i*hparams.num_mels:i*hparams.num_mels+hparams.num_mels,:])
				print(feature[i*hparams.num_mels:i*hparams.num_mels+hparams.num_mels,:].shape)

			print("###########################################################")



			for idx, i in enumerate(data_chuncks):
				
				
				if idx >= 11: break # take at most 8 chunks from one midi

				if num < 1400: # 4500 * 0.7
					set_name = 'train'
					train_test_valnum[0] += 1
				elif num < 1700: # 4500 * 0.15
					set_name = 'test'
					train_test_valnum[1] += 1
				elif num < 2000:
					set_name = 'valid'
					train_test_valnum[2] += 1
				else: # only take 4500 for each genre
					set_name = 'getout'
					break

				num += 1
				tot_mel_num[label] += 1

				save_name = GENRES[label] + '_' + str(k).zfill(4) + str(idx) + '.npy' # Classical_00011.npy
				print(save_name)
				save_path = os.path.join(hparams.feature_path, set_name, GENRES[label])
				# print('save_path: ', save_path)
				
				if not os.path.exists(save_path):
					os.makedirs(save_path)

				if i.shape[0] == 128 and i.shape[1] == 128: # num_mels = 128
				

					np.save(os.path.join(save_path, save_name), i.type(torch.FloatTensor))
					print(os.path.join(save_path, save_name))
					

				else:
					# print('error on file: ', file_name)
					err += 1

			# num += 1
			if set_name == 'getout': break



	print('genres tensor num [Blues,HipHopRap,Jazz,NewAge,Pop]:', tot_mel_num)
	print('train / test / valid num:', train_test_valnum)
	print('total error:', err)

	print('finished')

if __name__ == '__main__':
	main()