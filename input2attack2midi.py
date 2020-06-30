import torch.nn as nn
import torch.nn.functional as F
import torch.utils.data
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import torch
import matplotlib.pyplot as plt
from torchaudio import transforms
from torch import utils
import numpy as np
import random
# import torchsummary
from torch.optim import lr_scheduler
from os.path import *
from os import listdir
from tqdm import tqdm
from MIDIDataset import MIDIDataset # MIDIDataset FOR ATTACK
from ResNet import resnet50
# from CustomCNN import CustomCNN
import copy
from sklearn.preprocessing import normalize


import py_midicsv
import pandas as pd
import csv
import sys

torch.manual_seed(123)
import torch.nn as nn


#for GPU use
# INPUT npy ==> ATTACK ==> MIDI file

import os
# os.environ["CUDA_DEVICE_ORDER"]="PCI_BUS_ID"
# os.environ["CUDA_VISIBLE_DEVICES"]="0,1"



####################################################
GENRES = ['Classical','Rock', 'Country', 'GameMusic'] #best
num_genres = len(GENRES)
batch_size = 1 #attack

data_dir = "/data/drum/bestmodel/" #orig path
# data_dir = "/data/drum/attack_bestmodel/" #attacked path

# vloader = torch.load('/data/drum/bestmodel/dataset/train/train_loader.pt') #orig train
vloader = torch.load('/data/drum/bestmodel/dataset/test/valid_loader.pt') #orig valid

# for simulation
only_file = 'scn15_11_format0.mid'
only_genre = 'Classical'
# only_file = 'tetriskb.mid'
# only_genre = 'GameMusic'


input_total = []
output_total = []
fname_total = []
for v in vloader:
    for i in range(len(v[0])): #20
        input_total.append(torch.unsqueeze(v[0][i],0)) #torch [1,129,400,128]
        output_total.append(torch.unsqueeze(v[1][i],0)) #tensor [(#)]
    fname_total.extend(v[2])


for i, e in enumerate(fname_total):
    if only_file in e:
        input_total = [input_total[i]]
        output_total = [output_total[i]]
        fname_total = [fname_total[i]]
        break

print('########################################################')
print("==> DATA LOADED")
########################################################
###load model

# device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

loss_function = nn.CrossEntropyLoss()

model = resnet50(129, num_genres)
model.eval()
checkpoint = torch.load(data_dir + 'Res50_valloss_0.8801_acc_81.25.pt') #original model
# checkpoint = torch.load(data_dir + 'deepfool/Res50_valloss_0.7089444994926453_acc_81.13636363636364.pt') #adv training (model2)
# checkpoint = torch.load(data_dir + 'fgsm/Res50_val_TandAT_loss_0.8046790957450867_acc_81.5.pt')
model.load_state_dict(checkpoint['model.state_dict'])
print("==> BASE MODEL LOADED")


def fgsm_attack(input, epsilon, data_grad):
    #collect element-wise "sign" of the data gradient
    sign_data_grad = data_grad.sign()
    perturbed_input = input + epsilon*sign_data_grad
    perturbed_input = torch.clamp(perturbed_input, 0, 127)
    return perturbed_input

#
def vel_attack(input, epsilon, data_grad, random): #input -> tensor
    #FOR ZERO ATTACK - 모든 셀을 공격
    # sign_data_grad = data_grad.sign()
    # ep_mat = torch.zeros(input.shape)
    # rng = ep_mat + epsilon #all cells are epsilon
    # if(random):
    #     rn = torch.rand(1,129,400,128)
    #     rng = rn*epsilon
    #
    # perturbed_input = input + rng*sign_data_grad
    # perturbed_input = perturbed_input.round()
    # perturbed_input = torch.clamp(perturbed_input, 0, 127)
    # print(perturbed_input)

    #FOR NONZERO ATTACK - 이미 값이 있는 셀만 공격
    sign_data_grad = data_grad.sign()
    indices = torch.nonzero(input) #get all the attack points
    perturbed_input = input + 0*sign_data_grad
    for index in indices:
        i, j, k, l = index[0], index[1], index[2], index[3]
        orig_vel = int(input[i][j][k][l].item()) #int
        att_sign = int(sign_data_grad[i][j][k][l].item())
        if(att_sign != 0): #meaningless -> almost all nonzero
            max_vel = 127
            min_vel = 0
            rng = epsilon
            if (random):
                rn = np.random.rand()
                rng = rn*epsilon #ex) ep = 20
            perturbed_input[i][j][k][l] = orig_vel + att_sign * int(round(rng))
            if(perturbed_input[i][j][k][l].item() > max_vel): perturbed_input[i][j][k][l] = max_vel
            if(perturbed_input[i][j][k][l].item() < min_vel): perturbed_input[i][j][k][l] = min_vel

    return perturbed_input




def deepfool(input, out_init, max_iter, nzero ,overshoot = 5):
    indices = torch.nonzero(input)

    #model output (probability)
    f_out = out_init.detach().numpy().flatten()
    I = (np.array(f_out)).argsort()[::-1] #index of greatest->least  ex:[2, 0, 1, 3]
    label = I[0] #true class index

    #initialize variables
    input_shape = input.numpy().shape
    w = np.zeros(input_shape) # (1, 129, 400, 128)
    r_tot = np.zeros(input_shape)
    loop_i = 0
    k_i = label  # initialize as true class


    perturbed_input = copy.deepcopy(input)  #copy entire tensor object
    x = perturbed_input.clone().requires_grad_(True)
    fs = model(x) #forward
    # fs_list = [fs[0,I[k]] for k in range(num_genres)] #greatest -> least
    print("loop", end=": ")
    while k_i == label and loop_i < max_iter: #repeat until misclassify
        print("{}".format(loop_i), end=" ")

        pert = np.inf #find min perturb (comparison)
        #get true class gradient -> used in calculations
        fs[0, I[0]].backward(retain_graph=True)
        grad_orig = x.grad.data.numpy().copy()

        for k in range(1, num_genres): #find distance to closest class(hyperplane)

            #x.zero_grad()

            #get gradient of another class "k"
            fs[0, I[k]].backward(retain_graph=True)
            cur_grad = x.grad.data.numpy().copy()

            #set new w_k and new f_k (numpy)
            w_k = cur_grad - grad_orig
            f_k = (fs[0, I[k]] - fs[0, I[0]]).data.numpy()

            pert_k = abs(f_k) / np.linalg.norm(w_k.flatten())

            #determine w_k to use
            if pert_k < pert:
                pert = pert_k
                w = w_k


        #FINALLY we have min w & pert (= distance to closest hyperplane)
        #now compute r_i and r_tot
        r_i = (pert + 1e-4) * w / np.linalg.norm(w)


        # manual implementation
        r_i_scaled = r_i #initialize
        r_i_valid = np.zeros(input_shape)
        if(not nzero):  #non-empty cells
            for index in indices:
                i, j, k = index[1], index[2], index[3]
                if(r_i[0][i][j][k] != 0):
                    r_i_valid[0][i][j][k] = r_i[0][i][j][k] #copy cell

            #어택 후보4
            # r_i_sign = np.sign(r_i_valid)
            # r_i_scaled = r_i_sign*overshoot

            #어택 후보3
            # r_i_sign = np.sign(r_i_valid)
            # # normalize abs
            # r_i_abs = np.abs(r_i_valid)
            # r_i_norm = r_i_abs - np.min(r_i_abs) / np.ptp(r_i_abs)
            # r_i_scaled = r_i_norm * overshoot * r_i_sign

            #어택 후보2
            # #normalize to [-1,1]
            # r_i_norm = 2*(r_i_valid - np.min(r_i_valid)) / np.ptp(r_i_valid) -1  # np / (max - min)
            # #scale to [min, max]
            # r_i_scaled = r_i_norm * overshoot

            #어택 후보1
            # scale = 10
            # count = 0
            # while(len(np.where(np.abs(r_i_valid) > 1)[0]) < ((len(np.nonzero(r_i_valid)[0]))/3)): #threshold : half
            #     print("{}th: one digits :{} nonzero :{}".format(count,len(np.where(np.abs(r_i_valid) > 1)[0]),len(np.nonzero(r_i_valid)[0])))
            #     count += 1
            #     scale *= 10
            #     r_i_valid = r_i_valid * scale
            # r_i_scaled = np.int_(r_i_valid)  # goal: 1-2digit integer

            #FINAL...
            r_i_scaled = np.int_(r_i_valid*1e+4) #1-2digit inte
            # r_i_scaled = r_i_valid*1e+4


        r_tot = np.float32(r_tot + r_i_scaled) # r_tot += r_i

        #reset perturbed_input
        perturbed_input = input + torch.from_numpy(r_tot)
        perturbed_input = torch.clamp(perturbed_input, 0, 127)

        x = perturbed_input.clone().requires_grad_(True)
        fs = model(x)
        k_i = np.argmax(fs.data.numpy().flatten()) #new pred

        loop_i += 1


    print("")
    #double check
    # perturbed_input = torch.clamp(perturbed_input, 0, 127)
    r_tot = np.clip(np.abs(r_tot), 0, 127)
    return r_tot, loop_i, k_i, perturbed_input


def tempo_edge_attack(input, eps ,data_grad):
    sign_data_grad = data_grad.sign()

    # indices = torch.nonzero(input, as_tuple=True)  # get all the attack points
    indices = torch.nonzero(input, as_tuple=False)
    indices_np = np.array(indices)
    cur_ch = indices_np[0][1]
    perturbed_input = input.numpy().copy()

    save_pair = []
    # for i, index in enumerate(indices_np):
    # for i in range(1, len(indices_np)-1):
    for i in range(len(indices_np)): # 0 - len-1

        while(i < len(indices_np) and indices_np[i][1] == cur_ch):

            start, end = indices_np[i], indices_np[i]
            pitch = indices_np[i][3]
            i += 1
            while(i < len(indices_np) and indices_np[i][3] == pitch):
                end = indices_np[i] #cur pos
                i += 1  # update i -> next pos

            #check is len > 2
            if(start[2] < end[2] and start[3] == end[3]):
                save_pair.append([start, end]) #save pair
                # print("{}: {}".format(i,[start, end]))

            if(i < (len(indices_np)-1)):
                cur_ch = indices_np[i][1]
            else:
                cur_ch = -1


########## manipulate!! ###########
    for pair in save_pair:
        begin, until = pair[0], pair[1]
        b_vel = perturbed_input[0][begin[1]][begin[2]][begin[3]]
        u_vel = perturbed_input[0][until[1]][until[2]][until[3]]
        rng = eps
        if (begin[2] > rng and until[2] < (400-rng)):
            for i in range(rng):
                perturbed_input[0][begin[1]][begin[2]-i][begin[3]] = b_vel
                perturbed_input[0][until[1]][until[2]+i][until[3]] = u_vel

    perturbed_input = torch.from_numpy(perturbed_input)
    return perturbed_input

##########################################################################

def test(model, epsilon):

    adv_rounded = []
    adv_fname = []
    correct = 0
    orig_wrong = 0

    # for i,val in enumerate(tqdm(val_loader)):
    for i, (v_in, v_out, v_fn) in enumerate(zip(input_total, output_total, fname_total)):
        model.eval()
        data, target, name = v_in, v_out, v_fn.replace("/", "_")

        # data, target = data.to(device), target.to(device)
        data = data.detach()
        data.requires_grad = True #for attack
        init_out = model(data)
        init_pred = torch.max(init_out, 1)[1].view(target.size()).data
        # _, init_pred = torch.max(init_out.data, 1)

        #if correct, skip
        if(init_pred.item() != target.item()):
            orig_wrong += 1
            # print("{}: wrong! --- pred:{} orig:{}]".format(i,init_pred.item(),target.item()))
            continue
        # print("{}: correct!--- pred:{} orig:{}]".format(i,init_pred.item(),target.item()))


        #if wrong, ATTACK
        loss = loss_function(init_out, target)  # compute loss
        model.zero_grad()
        loss.backward()
        data_grad = data.grad.data

        #VEL ATTACKS
        # perturbed_data = vel_attack(data, epsilon, data_grad, True) # vel --> fgsm random attack
        perturbed_data = vel_attack(data, epsilon, data_grad, False) # vel --> fgsm sign grad attack
        # perturbed_data = tempo_edge_attack(data.detach(), epsilon, data_grad) #tempo edge attack
        #RERUN MODEL
        new_out = model(perturbed_data)
        # confidence = torch.softmax(new_out[0], dim=0)
        # target_confidence = torch.max(confidence).item() * 100
        new_pred = torch.max(new_out, 1)[1].view(target.size()).data
        # print(new_out)

        #get orig data
        # orig_data = data.squeeze().numpy()
        np_vel = perturbed_data.squeeze().detach().numpy() #(129 400 128)

        # check for success
        if new_pred.item() == target.item():
            correct += 1
        else:
            print("Origin Genre:", GENRES[int(target.item())])
            print("After Attack:", GENRES[int(new_pred.item())]) # 'with Confidence:', target_confidence
            print()
            # pass
        #np.save("/data/attack_test/pitch_" + each_file, np_pitch)  # save as .npy
        #     np.save("/data/attack_test/time_" + each_file, np_time)  # save as .npy
            np.save("/data/scn15/vel_" +  name, np_vel)  # save as .npy | "_[" + str(epsilon) +"]"+
        #     np.save("/data/attack_test/vel_" + each_file + "_[0]" , orig_data)  # save as .npy

        # DEEPFOOL(LAST)
        # nonzero = False
        # data_nograd = data.detach() #lose gradient
        # r_tot, iter_num, wrong_pred, perturbed_data = deepfool(data_nograd, init_out, 10, nonzero)
        # perturbed_data = np.int_(perturbed_data.squeeze().numpy()) #.astype(np.int8)
        # r_tot = np.int_(r_tot.squeeze()) #.astype(np.int8)
        # if(wrong_pred != target): #check for success
        #     # pass #success
        #     np.save("/data/attacks/vel_deepfool2/valid/vel_" + str(name), perturbed_data) #save as .npy
        #     np.save("/data/attacks/vel_deepfool2/valid_noise/noise_" + str(name), r_tot)
        # else: #failed to attack
        #     correct += 1

        # print("{}th data: {}".format(i+1, name))
        # print("{}".format(i+1))
    # print("files saved!")
    return adv_rounded, adv_fname, orig_wrong, correct


##########################################################
#run attack

accuracies = []
# epsilons = [0,2,4,6,8,10,12,14,16,18,20, 22, 24, 26, 28, 30,32,34,36,38,40] #for vel attacks
# epsilons = [5,10,15,20,25,30,35,40,45,50,55,60,65,70]
epsilons = [20]
# epsilons = [3,4,5,6] #for tempo
# epsilons = [0] #for deepfool
for ep in tqdm(epsilons):
#
    print("Epsilon: {}".format(ep))
    rounded, fname, orig_wrong, correct = test(model, ep)
    denom = len(input_total)
    orig_acc = (denom - orig_wrong) / denom
    final_acc = correct / float(denom)
    # print("Before: {} / {} = {}".format(denom - orig_wrong, denom, orig_acc))
    # print("After: {} / {} = {}".format(correct, denom, final_acc))
#
#     #for plt
    accuracies.append(final_acc)
    # examples.append(ex)


#Draw Results
# plt.figure(figsize=(5,5))
# plt.plot(epsilons, accuracies, "*-")
# plt.yticks(np.arange(0, 1.1, step=0.1))
# plt.xticks(np.arange(0, 7, step=1))
# plt.title("Accuracy vs +- Cell Range")
# plt.xlabel("Cell Range")
# plt.ylabel("Accuracy")
# plt.show()

#Draw Results
# plt.figure(figsize=(5,5))
# plt.plot(epsilons, accuracies, "*-")
# plt.yticks(np.arange(0, 1.1, step=0.1))
# plt.xticks(np.arange(0, 70, step=5))
# plt.title("Accuracy vs Epsilon")
# plt.xlabel("Epsilon")
# plt.ylabel("Accuracy")
# plt.show()



##########################################################################################
##########################################################################################

# GENRES = ['Classical', 'Rock', 'Country', 'GameMusic']
SAVED_NUMPY_PATH = '/data/midi820_128channel/'

### Set File directory
origin_midi_dir = '/data/3genres/'  # Get the Hedaer and other data at original Midi Data
# classical_numpy = 'C:/Users/hahal/PycharmProjects/MidiClass/attack_npy_filename/Classical_input.npy'
# classical_name_numpy = 'C:/Users/hahal/PycharmProjects/MidiClass/attack_npy_filename/Classical_filename.npy'
output_file_dir = '/data/scn15/'
# csv_output_dir = './attack2midi/csv/'
ATTACK_PATH = '/data/scn15/'


# --------------------------------------------------------------------------
# origin_midi_dir = '' #Get the Hedaer and other data at original Midi Data
# classical_numpy = 'C:\\Users\\icarus\\Desktop\\Rock_input.npy'
# classical_name_numpy = 'C:\\Users\\icarus\\Desktop\\Rock_filename.npy'
# attack = 'C:\\Users\\icarus\\Desktop\\ep_0.025_orig.npy'
# output_file_dir = 'C:\\Users\\icarus\\Desktop\\Alborada del Gracioso.mid'
# output_file_dir2 = 'C:\\Users\\icarus\\Desktop\\Andante alla marcia.mid'
# csv_output_dir = 'C:\\Users\\icarus\\Desktop\\New_Midi.csv'
# output_file_dir = '/data/csv_to_midi/Classical/'
# csv_output_dir = '/data/checking_csv/'


# Instrument mapping for 'gm.dls' (Windows Default Soundfont)
# 50: Harmonica --> Piccolo, 57: Shehnai --> Clarinet
# program_num_map = {0: 0, 1: 64, 2: 24, 3: 1, 4: 34, 5: 40, 6: 105, 7: 69, 8: 64, 9: 85,
#                    10: 68, 11: 32, 12: 27, 13: 57, 14: 48, 15: 60, 16: 18, 17: 35, 18: 75, 19: 7,
#                    20: 47, 21: 43, 22: 12, 23: 61, 24: 73, 25: 11, 26: 21, 27: 16, 28: 20, 29: 56,
#                    30: 6, 31: 71, 32: 79, 33: 15, 34: 74, 35: 104, 36: 42, 37: 106, 38: 58, 39: 107,
#                    40: 66, 41: 46, 42: 9, 43: 77, 44: 41, 45: 14, 46: 72, 47: 70, 48: 114, 49: 113,
#                    50: 72, 51: 108, 52: 67, 53: 78, 54: 109, 55: 8, 56: 115, 57: 71, 58: 116, 59: 13
#                    }

# functions
def start_track_string(track_num):
    return str(track_num) + ', 0, Start_track\n'


def title_track_string(track_num):
    return str(track_num) + ', 0, Title_t, "Test file"\n'


def program_c_string(track_num, channel, program_num):
    return str(track_num) + ', 0, Program_c, ' + str(channel) + ', ' + str(int(program_num)) + '\n'


def note_on_event_string(track_num, delta_time, channel, pitch, velocity):
    return str(track_num) + ', ' + str(delta_time) + ', Note_on_c, ' + str(channel) + ', ' + str(pitch) + ', ' + str(
        velocity) + '\n'


def note_off_event_string(track_num, delta_time, channel, pitch, velocity):
    return str(track_num) + ', ' + str(delta_time) + ', Note_off_c, ' + str(channel) + ', ' + str(pitch) + ', ' + str(
        velocity) + '\n'


def end_track_string(track_num, delta_time):
    return str(track_num) + ', ' + str(delta_time) + ', End_track\n'


end_of_file_string = '0, 0, End_of_file\n'

'''
count = 0
good_files = []
num = 0
vel = 0
noise = 0
for file in os.listdir(ATTACK_PATH):
   skip = 0
   if os.path.isfile(os.path.join(ATTACK_PATH, file)):
      loaded = np.load(os.path.join(ATTACK_PATH, file))
      if num == 30: break

      if 'vel' in file: vel += 1
      elif 'noise' in file: noise += 1


      for i in range(0,129):
         for j in range(0,400):
            for k in range(0, 128):
               if not (0 <= loaded[i][j][k] <= 128):
                  # print('loaded [i,j,k] =','[',i,'',j,'',k,'] => ', loaded[i][j][k])
                  count += 1
                  skip = 1
                  break

            if skip == 1: break
         if skip == 1: break

      if skip == 0: good_files.append(file)
      num += 1

for file in good_files:
   print(file)

print('# of good file:', count)
print('vel:', vel)
print('noise:', noise)
'''
'''
# load npy for each genres
for genre in GENRES:

   changed_num = 0

   print('##############################')
   print('GENRE start:', genre)

   saved_name_numpy = SAVED_NUMPY_PATH + genre + '_filename.npy'
   saved_numpy = SAVED_NUMPY_PATH + genre + '_input.npy'

   load_full_data = np.load(saved_numpy)
   load_full_file_names = np.load(saved_name_numpy)

   # print(len(load_full_data)) # 100
   # print(load_full_data.shape) # (100, 400, 128)

   for idx in range(len(load_full_data)):

     if changed_num == 30: break # check 30 for each genre first
     changed_num += 1

     load_data = load_full_data[idx]
     load_file_name = load_full_file_names[idx]
     only_file_name = load_file_name.split('/')[4]
     genre = load_file_name.split('/')[3]
     # print(genre)
     # print(only_file_name)

     # origin_midi_dir = origin_midi_dir + genre + '/'  # add genre to path
'''

new_csv_string = []

## Set all of the new_csv_string
# Header: Track, Delta Time, Type, Number of Tracks, Ticks for Quater Note
total_track = 0
# def header_string(total_track = 0): # We should put tempo, in real data from origin midi data
#     return '0, 0, Header, 1, ' + str(total_track) + ', 168\n'
track_num = 1  # Set the Track number
# track_num + string

program_num = 0
delta_time = 0
channel = 0
pitch = 60
velocity = 90

# ## Read numpy_array with npy
# instrument_dict = {}
# for channel_instrument in range(0,128):
#     for row in range(0, 400):
#         for col in range(0, 128):
#             if channel_instrument in instrument_dict.keys() or load_data[channel_instrument][row][col] == -1:
#                 continue
#             else:
#                 instrument_dict[channel_instrument] = 1

# total_track = len(instrument_dict) + 2  # instr num + two -1(one for header, one for tempo & key & title ....)


off_note = 0
# attack_type = ['vel', 'noise']  # 'orig', 'pitch', 'time',
# only_file_name = 'alb_esp4_format0.mid'
success_num = 0

for file in os.listdir(ATTACK_PATH):
    if os.path.isfile(os.path.join(ATTACK_PATH, file)):

        # for simulation one music
        if file != 'vel_' + only_genre + '_' + only_file + '.npy': continue

        if 'vel' in file:
            atype = 'vel'
        elif 'noise' in file:
            continue
        else: # origin input2midi
          atype = 'origin'

        only_file_name = file.replace(atype + '_', '').replace('.npy', '')

        for genre in GENRES:
            if genre in only_file_name:
                only_file_name = only_file_name.replace(genre + '_', '')
                break


        # print(only_file_name)

        new_csv_string = []
        load_data = np.load(os.path.join(ATTACK_PATH, file))

        origin_file = origin_midi_dir + only_file_name
        # print("Original file:", only_file_name)

        try:
            origin_file_csv = py_midicsv.midi_to_csv(origin_file)
        except:
            continue

        else:
            print('########################################################')
            print('########################################################')
            print('Converting FGSM attacked input to MIDI..........')
            # print("current file:", file)
            # for string in origin_file_csv:
            #    if 'Program_c' in string: print(string)
            total_track = 2
            current_used_instrument = [-1, -1]
            # find total track num
            for instrument_num, lst in enumerate(load_data):  # instrument_num : 0-127
                if np.sum(lst) != (off_note) * 400 * 128:
                    total_track += 1
                    current_used_instrument.append(instrument_num)

            # slower by 4.8
            header = origin_file_csv[0].split(', ')
            # print('Before header:', header)
            header[-1] = str(int(int(header[-1][:-1]) / 4.0)) + '\n'
            header[-2] = str(int(total_track))
            # print('After header:', header)
            new_csv_string.append(', '.join(header))  # header_string(total_track) + change last to 168 (too fast)
            new_csv_string.append(origin_file_csv[1])  # start_track_string(track_num)

            for string in origin_file_csv:
                if 'SMPTE_offset' in string:
                    # print(string)
                    continue
                elif 'Time_signature' in string or 'Tempo' in string:
                    new_csv_string.append(string)

                elif 'Program_c' in string:
                    break

            new_csv_string.append(end_track_string(track_num, delta_time))
            # print('Before Real Data Part:')
            # for string in new_csv_string: print(string)

            # ## Real Data Part # deleted after add 128 instrument dim
            # current_used_instrument = [-1, -1]
            # for instrument_num in instrument_dict.keys():
            #     current_used_instrument.append(instrument_num)
                # print(lst.shape)

            # print(total_track)

            # Set the track_string_list to identify different instrument time line
            track_string_list = [[] for i in range(0, total_track)]
            track_string_list[0].append(-1)  # To Generate Error -> Header File
            track_string_list[1].append(-1)  # To Generate Error -> Meta File

            note_on_list = [[] for i in range(0, total_track)]
            note_on_list[0].append(-1)
            note_on_list[1].append(-1)

            note_off_list = [[] for i in range(0, total_track)]
            note_off_list[0].append(-1)
            note_off_list[1].append(-1)

            # print(load_data.shape[0], ' ', load_data.shape[1], ' ', load_data.shape[2])
            for channel_instrument in range(0, load_data.shape[0]):
                for row in range(0, load_data.shape[1]):
                    for col in range(0, load_data.shape[2]):

                        if load_data[channel_instrument][row][col] == off_note:
                            continue
                        else:
                            # Set the different condition for attacked Midi Files
                            # print('music21 instrument:', load_data[row][col]) # 0-59
                            # print('py_midicsv instrument:', program_num_map[load_data[row][col]])

                            if len(track_string_list[current_used_instrument.index(channel_instrument)]) != 0:
                                program_num = channel_instrument  # program_num = instrment num
                                pitch = col
                                channel = 0
                                delta_time = 50 * row
                                end_delta_time = 50 * (row + 1)
                                velocity = int(
                                    load_data[channel_instrument][row][col])  # TODO: We should consider later
                                note_on_list[track_num].append([track_num, delta_time, channel, pitch, velocity])
                                note_off_list[track_num].append([track_num, end_delta_time, channel, pitch, velocity])
                            else:
                                # Set the track_string_list new track header - program_c event
                                track_num = current_used_instrument.index(channel_instrument)
                                if channel_instrument == 128:
                                    program_num = 1
                                else:
                                    program_num = channel_instrument
                                channel = 0
                                pitch = col
                                delta_time = 50 * row
                                end_delta_time = 50 * (row + 1)
                                velocity = int(
                                    load_data[channel_instrument][row][col])
                                track_string_list[track_num].append(start_track_string(track_num))
                                track_string_list[track_num].append(title_track_string(track_num))
                                track_string_list[track_num].append(program_c_string(track_num, channel, program_num))
                                note_on_list[track_num].append([track_num, delta_time, channel, pitch, velocity])
                                note_off_list[track_num].append([track_num, end_delta_time, channel, pitch, velocity])

                    for num in range(2, len(note_on_list)):  # num = track num
                        for notes in range(0, len(note_on_list[num])):
                            track_string_list[num].append(
                                note_on_event_string(note_on_list[num][notes][0], note_on_list[num][notes][1],
                                                     note_on_list[num][notes][2], note_on_list[num][notes][3],
                                                     note_on_list[num][notes][4]))
                    for num in range(2, len(note_off_list)):
                        for notes in range(0, len(note_off_list[num])):
                            track_string_list[num].append(
                                note_off_event_string(note_off_list[num][notes][0], note_off_list[num][notes][1],
                                                      note_off_list[num][notes][2], note_off_list[num][notes][3],
                                                      note_off_list[num][notes][4]))
                    note_on_list = [[] for i in range(0, total_track)]
                    note_off_list = [[] for i in range(0, total_track)]

            end_delta_time = 400 * 50
            for i in range(2, len(track_string_list)):
                for j in track_string_list[i]:
                    new_csv_string.append(j)
                new_csv_string.append(end_track_string(i, end_delta_time))
            new_csv_string.append(end_of_file_string)
            # print('NEW STRING')

            # data = pd.DataFrame(new_csv_string)
            # data.to_csv(csv_output_dir,index = False)

            midi_object = py_midicsv.csv_to_midi(new_csv_string)

            with open(output_file_dir + '/New_' + atype + '_' + only_file_name, "wb") as output_file:
                midi_writer = py_midicsv.FileWriter(output_file)
                midi_writer.write(midi_object)
                print('CSV to Midi File success!!')

                success_num += 1

            # # For Cheking Error Data, Represent to csv files
            # csv_string = py_midicsv.midi_to_csv(output_file_dir + 'New_' + only_file_name)
            # tmp_list = []
            # for i in range(0, len(csv_string)):
            #     temp = np.array(csv_string[i].replace("\n", "").replace(" ", "").split(","))
            #     tmp_list.append(temp)
            # data = pd.DataFrame(tmp_list)
            # data.to_csv(csv_output_dir + 'New_' + only_file_name[:-4] + '.csv', header=False, index=False)

            # break # for checking one midi