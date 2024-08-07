import re
import string
from unicodedata import normalize
import numpy


def load_doc(filename):
    file = open(filename, mode='rt', encoding='utf-8')
    text = file.read()
    file.close()
    return text



def to_pairs(doc):
    lines = doc.strip().split('\n')
    pairs = [line.split('\t') for line in  lines]
    return pairs

def clean_data(lines):
    cleaned = list()
    re_print = re.compile('[^%s]' % re.escape(string.printable))
    table = str.maketrans('', '', string.punctuation)
    for pair in lines:
        clean_pair = list()
        for line in pair:
            line = normalize('NFD', line).encode('ascii', 'ignore')
            line = line.decode('UTF-8')
            line = line.split()
            line = [word.lower() for word in line]
            line = [word.translate(table) for word in line]
            line = [re_print.sub('', w) for w in line]
            line = [word for word in line if word.isalpha()]
            clean_pair.append(' '.join(line))
        cleaned.append(clean_pair)
    return numpy.array(cleaned)

filename = "Data/spa.txt"


n_train = 20000



doc = load_doc(filename)

pairs = to_pairs(doc)


clean_pairs = clean_data(pairs)[0:n_train, :]



for i in range(3000, 3010):
    print('[' + clean_pairs[i, 0] + '] => [' + clean_pairs[i, 1] + ']')



input_texts = clean_pairs[:, 0]
target_texts = ['\t' + text + '\n' for text in clean_pairs[:, 1]]
print('Length of input_texts:  ' + str(input_texts.shape))
print('Length of target_texts: ' + str(input_texts.shape))


max_encoder_seq_length = max(len(line) for line in input_texts)
max_decoder_seq_length = max(len(line) for line in target_texts)

print('max length of input  sentences: %d' % (max_encoder_seq_length))
print('max length of target sentences: %d' % (max_decoder_seq_length))

from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences


def text2sequences(max_len, lines):
    tokenizer = Tokenizer(char_level=True, filters='')
    tokenizer.fit_on_texts(lines)
    seqs = tokenizer.texts_to_sequences(lines)
    seqs_pad = pad_sequences(seqs, maxlen=max_len, padding='post')
    return seqs_pad, tokenizer.word_index


encoder_input_seq, input_token_index = text2sequences(max_encoder_seq_length,
                                                      input_texts)
decoder_input_seq, target_token_index = text2sequences(max_decoder_seq_length,
                                                       target_texts)

print('shape of encoder_input_seq: ' + str(encoder_input_seq.shape))
print('shape of input_token_index: ' + str(len(input_token_index)))
print('shape of decoder_input_seq: ' + str(decoder_input_seq.shape))
print('shape of target_token_index: ' + str(len(target_token_index)))





num_encoder_tokens = len(input_token_index) + 1
num_decoder_tokens = len(target_token_index) + 1

print('num_encoder_tokens: ' + str(num_encoder_tokens))
print('num_decoder_tokens: ' + str(num_decoder_tokens))

target_texts[100]

decoder_input_seq[100, :]

from tensorflow.keras.utils import to_categorical

def onehot_encode(sequences, max_len, vocab_size):
    n = len(sequences)
    data = numpy.zeros((n, max_len, vocab_size))
    for i in range(n):
        data[i, :, :] = to_categorical(sequences[i], num_classes=vocab_size)
    return data

encoder_input_data = onehot_encode(encoder_input_seq, max_encoder_seq_length, num_encoder_tokens)
decoder_input_data = onehot_encode(decoder_input_seq, max_decoder_seq_length, num_decoder_tokens)

decoder_target_seq = numpy.zeros(decoder_input_seq.shape)
decoder_target_seq[:, 0:-1] = decoder_input_seq[:, 1:]
decoder_target_data = onehot_encode(decoder_target_seq,
                                    max_decoder_seq_length,
                                    num_decoder_tokens)

print(encoder_input_data.shape)
print(decoder_input_data.shape)

from tensorflow.keras.layers import Input, LSTM
from tensorflow.keras.models import Model
from keras.layers import Bidirectional, Concatenate

latent_dim = 256

encoder_inputs = Input(shape=(None, num_encoder_tokens),
                       name='encoder_inputs')

encoder_bilstm = Bidirectional(LSTM(latent_dim, return_state=True, dropout=0.5, name='encoder_lstm'))
_, forward_h, forward_c, backward_h, backward_c = encoder_bilstm(encoder_inputs)

state_h = Concatenate()([forward_h, backward_h])
state_c = Concatenate()([forward_c, backward_c])

encoder_model = Model(inputs=encoder_inputs, outputs=[state_h, state_c], name='encoder')

def encoder(num_encoder_tokens, latent_dim):
    encoder_inputs = Input(shape=(None, num_encoder_tokens), name='encoder_inputs')

    encoder_bilstm = Bidirectional(LSTM(latent_dim, return_state=True, dropout=0.5, name='encoder_lstm'))
    _, forward_h, forward_c, backward_h, backward_c = encoder_bilstm(encoder_inputs)

    state_h = Concatenate()([forward_h, backward_h])
    state_c = Concatenate()([forward_c, backward_c])

    encoder_model = Model(inputs=encoder_inputs, outputs=[state_h, state_c], name='encoder')
    return encoder_model

from IPython.display import SVG
from keras.utils import model_to_dot, plot_model

SVG(model_to_dot(encoder_model, show_shapes=False).create(prog='dot', format='svg'))

plot_model(
    model=encoder_model, show_shapes=False,
    to_file='encoder.pdf'
)

encoder_model.summary()


from tensorflow.keras.layers import Input, LSTM, Dense
from tensorflow.keras.models import Model

new_latent_dim = latent_dim*2

decoder_input_h = Input(shape=(new_latent_dim,), name='decoder_input_h')
decoder_input_c = Input(shape=(new_latent_dim,), name='decoder_input_c')
decoder_input_x = Input(shape=(None, num_decoder_tokens), name='decoder_input_x')


decoder_lstm = LSTM(new_latent_dim, return_sequences=True,
                    return_state=True, dropout=0.5, name='decoder_lstm')
decoder_lstm_outputs, state_h, state_c = decoder_lstm(decoder_input_x,
                                                      initial_state=[decoder_input_h, decoder_input_c])


decoder_dense = Dense(num_decoder_tokens, activation='softmax', name='decoder_dense')
decoder_outputs = decoder_dense(decoder_lstm_outputs)


decoder_model = Model(inputs=[decoder_input_x, decoder_input_h, decoder_input_c],
                      outputs=[decoder_outputs, state_h, state_c],
                      name='decoder')
def decoder(num_decoder_tokens, new_latent_dim):
    decoder_input_h = Input(shape=(new_latent_dim,), name='decoder_input_h')
    decoder_input_c = Input(shape=(new_latent_dim,), name='decoder_input_c')
    decoder_input_x = Input(shape=(None, num_decoder_tokens), name='decoder_input_x')

    decoder_lstm = LSTM(new_latent_dim, return_sequences=True,
                        return_state=True, dropout=0.5, name='decoder_lstm')
    decoder_lstm_outputs, state_h, state_c = decoder_lstm(decoder_input_x,
                                                        initial_state=[decoder_input_h, decoder_input_c])

    decoder_dense = Dense(num_decoder_tokens, activation='softmax', name='decoder_dense')
    decoder_outputs = decoder_dense(decoder_lstm_outputs)

    decoder_model = Model(inputs=[decoder_input_x, decoder_input_h, decoder_input_c],
                        outputs=[decoder_outputs, state_h, state_c],
                        name='decoder')
    return decoder_lstm, decoder_dense, decoder_model


from IPython.display import SVG
from keras.utils import model_to_dot, plot_model

SVG(model_to_dot(decoder_model, show_shapes=False).create(prog='dot', format='svg'))

plot_model(
   model=decoder_model, show_shapes=False,
    to_file='decoder.pdf'
)

decoder_model.summary()

encoder_input_x = Input(shape=(None, num_encoder_tokens), name='encoder_input_x')
decoder_input_x = Input(shape=(None, num_decoder_tokens), name='decoder_input_x')

encoder_final_states = encoder_model([encoder_input_x])
decoder_lstm_output, _, _ = decoder_lstm(decoder_input_x, initial_state=encoder_final_states)
decoder_pred = decoder_dense(decoder_lstm_output)

model = Model(inputs=[encoder_input_x, decoder_input_x],
              outputs=decoder_pred,
              name='model_training')

def encoder_decoder(latent_dim, new_latent_dim, num_encoder_tokens, num_decoder_tokens):
    encoder_input_x = Input(shape=(None, num_encoder_tokens), name='encoder_input_x')
    decoder_input_x = Input(shape=(None, num_decoder_tokens), name='decoder_input_x')
    encoder_model = encoder(num_encoder_tokens, latent_dim)
    decoder_lstm, decoder_dense, decoder_model = decoder(num_decoder_tokens,new_latent_dim)
    encoder_final_states = encoder_model([encoder_input_x])
    decoder_lstm_output, _, _ = decoder_lstm(decoder_input_x, initial_state=encoder_final_states)
    decoder_pred = decoder_dense(decoder_lstm_output)    
    model = Model(inputs=[encoder_input_x, decoder_input_x],
              outputs=decoder_pred,
              name='model_training')
    return encoder_model,decoder_model,model


from IPython.display import SVG
from keras.utils import model_to_dot, plot_model

SVG(model_to_dot(model, show_shapes=False).create(prog='dot', format='svg'))

plot_model(
    model=model, show_shapes=False,
    to_file='model_training.pdf'
)

model.summary()

print('shape of encoder_input_data' + str(encoder_input_data.shape))
print('shape of decoder_input_data' + str(decoder_input_data.shape))
print('shape of decoder_target_data' + str(decoder_target_data.shape))




model.compile(optimizer='rmsprop', loss='categorical_crossentropy')

model.fit([encoder_input_data, decoder_input_data], 
          decoder_target_data,                       
          batch_size=64, epochs=50, validation_split=0.2)

model.save('seq2seq.h5')

reverse_input_char_index = dict((i, char) for char, i in input_token_index.items())
reverse_target_char_index = dict((i, char) for char, i in target_token_index.items())


def decode_sequence(input_seq):
    states_value = encoder_model.predict(input_seq)

    target_seq = numpy.zeros((1, 1, num_decoder_tokens))
    target_seq[0, 0, target_token_index['\t']] = 1.

    stop_condition = False
    decoded_sentence = ''
    while not stop_condition:
        output_tokens, h, c = decoder_model.predict([target_seq] + states_value)
        temperature = .25
        pred = output_tokens[0, -1, :].astype('float64')
        pred = pred ** (1/temperature)
        pred = pred / numpy.sum(pred) 
        pred[0] = 0
        sampled_token_index = numpy.argmax(numpy.random.multinomial(1,pred,1))
        sampled_char = reverse_target_char_index[sampled_token_index]
        decoded_sentence += sampled_char

        if (sampled_char == '\n' or
           len(decoded_sentence) > max_decoder_seq_length):
            stop_condition = True

        target_seq = numpy.zeros((1, 1, num_decoder_tokens))
        target_seq[0, 0, sampled_token_index] = 1.

        states_value = [h, c]

    return decoded_sentence


for seq_index in range(2100, 2120):
    input_seq = encoder_input_data[seq_index: seq_index + 1]
    decoded_sentence = decode_sequence(input_seq)
    print('-')
    print('English:       ', input_texts[seq_index])
    print('Spanish (true): ', target_texts[seq_index][1:-1])
    print('Spanish (pred): ', decoded_sentence[0:-1])


input_sentence = 'I love you'
input_text = [input_sentence]
input_sequence, _ = text2sequences(max_encoder_seq_length,input_text)

input_x = onehot_encode(input_sequence, max_encoder_seq_length, num_encoder_tokens)

translated_sentence = decode_sequence(input_x)

print('source sentence is: ' + input_sentence)
print('translated sentence is: ' + translated_sentence)



import sklearn 
from tensorflow.keras import optimizers
import nltk
n_train = 40000
clean_pairs = clean_data(pairs)[0:n_train, :]
input_texts = clean_pairs[:, 0]
target_texts = ['\t' + text + '\n' for text in clean_pairs[:, 1]]

input_texts_shuffle, target_texts_shuffle = sklearn.utils.shuffle(input_texts, target_texts)
length = len(input_texts_shuffle)
first_index = int(.6*length)
second_index = int(.8*length)

input_texts_train = input_texts_shuffle[:first_index]
input_texts_val = input_texts_shuffle[first_index:second_index]
input_texts_test = input_texts_shuffle[second_index:]


target_texts_train = target_texts_shuffle[:first_index]
target_texts_val = target_texts_shuffle[first_index:second_index]
target_texts_test = target_texts_shuffle[second_index:]

max_encoder_seq_length = max(len(line) for line in input_texts)
max_decoder_seq_length = max(len(line) for line in target_texts)

tokenizer = Tokenizer(char_level=True, filters='')
tokenizer.fit_on_texts(input_texts_train)
seqs = tokenizer.texts_to_sequences(input_texts_train)

input_token_index_train = tokenizer.word_index
encoder_input_seq_train = pad_sequences(seqs, maxlen=max_encoder_seq_length, padding='post')

seqs = tokenizer.texts_to_sequences(input_texts_val)
encoder_input_seq_val = pad_sequences(seqs, maxlen=max_encoder_seq_length, padding='post')
tokenizer.word_index = input_token_index_train

seqs = tokenizer.texts_to_sequences(input_texts_test)
encoder_input_seq_test = pad_sequences(seqs, maxlen=max_encoder_seq_length, padding='post')
tokenizer.word_index = input_token_index_train

tokenizer1 = Tokenizer(char_level=True, filters='')
tokenizer1.fit_on_texts(target_texts_train)
seqs = tokenizer1.texts_to_sequences(target_texts_train)
target_token_index_train = tokenizer1.word_index
decoder_input_seq_train = pad_sequences(seqs, maxlen=max_decoder_seq_length, padding='post')

seqs = tokenizer1.texts_to_sequences(target_texts_val)
decoder_input_seq_val = pad_sequences(seqs, maxlen=max_decoder_seq_length, padding='post')
tokenizer1.word_index = target_token_index_train

seqs = tokenizer1.texts_to_sequences(target_texts_test)
decoder_input_seq_test = pad_sequences(seqs, maxlen=max_decoder_seq_length, padding='post')
tokenizer1.word_index = target_token_index_train

num_encoder_tokens_train = len(input_token_index_train) + 1
num_decoder_tokens_train = len(target_token_index_train) + 1

encoder_input_data_train = onehot_encode(encoder_input_seq_train, max_encoder_seq_length, num_encoder_tokens_train)
decoder_input_data_train = onehot_encode(decoder_input_seq_train, max_decoder_seq_length, num_decoder_tokens_train)

decoder_target_seq_train = numpy.zeros(decoder_input_seq_train.shape)
decoder_target_seq_train[:, 0:-1] = decoder_input_seq_train[:, 1:]
decoder_target_data_train = onehot_encode(decoder_target_seq_train,
                                    max_decoder_seq_length,
                                    num_decoder_tokens_train)

encoder_input_data_val = onehot_encode(encoder_input_seq_val, max_encoder_seq_length, num_encoder_tokens_train)
decoder_input_data_val = onehot_encode(decoder_input_seq_val, max_decoder_seq_length, num_decoder_tokens_train)

decoder_target_seq_val = numpy.zeros(decoder_input_seq_val.shape)
decoder_target_seq_val[:, 0:-1] = decoder_input_seq_val[:, 1:]
decoder_target_data_val = onehot_encode(decoder_target_seq_val,
                                    max_decoder_seq_length,
                                    num_decoder_tokens_train)


encoder_input_data_test = onehot_encode(encoder_input_seq_test, max_encoder_seq_length, num_encoder_tokens_train)
decoder_input_data_test = onehot_encode(decoder_input_seq_test, max_decoder_seq_length, num_decoder_tokens_train)

decoder_target_seq_test = numpy.zeros(decoder_input_seq_test.shape)
decoder_target_seq_test[:, 0:-1] = decoder_input_seq_test[:, 1:]
decoder_target_data_test = onehot_encode(decoder_target_seq_test,
                                    max_decoder_seq_length,
                                    num_decoder_tokens_train)

print(encoder_input_data_train.shape)
print(encoder_input_data_val.shape)
print(encoder_input_data_test.shape)

encoder_model1, decoder_model1, model1 = encoder_decoder(latent_dim, new_latent_dim, num_encoder_tokens_train, num_decoder_tokens_train)
encoder_model2, decoder_model2, model2 = encoder_decoder(latent_dim, new_latent_dim, num_encoder_tokens_train, num_decoder_tokens_train)
encoder_model3, decoder_model3, model3 = encoder_decoder(latent_dim, new_latent_dim, num_encoder_tokens_train, num_decoder_tokens_train)

model1.compile(optimizer=optimizers.RMSprop(learning_rate=.00001), loss='categorical_crossentropy')
model1.fit([encoder_input_data_train, decoder_input_data_train],  
          decoder_target_data_train,                     
          batch_size=64, epochs=50)

model2.compile(optimizer=optimizers.RMSprop(learning_rate=.0001), loss='categorical_crossentropy')
model2.fit([encoder_input_data_train, decoder_input_data_train],  
          decoder_target_data_train,                       
          batch_size=64, epochs=50)
model2.evaluate([encoder_input_data_val, decoder_input_data_val], decoder_target_data_val)

model3.compile(optimizer=optimizers.RMSprop(learning_rate=.001), loss='categorical_crossentropy')
model3.fit([encoder_input_data_train, decoder_input_data_train],  
          decoder_target_data_train,                       
          batch_size=64, epochs=50)
model3.evaluate([encoder_input_data_val, decoder_input_data_val], decoder_target_data_val)

print(".00001 LR")
model1.evaluate([encoder_input_data_val, decoder_input_data_val], decoder_target_data_val)
print(".0001 LR")
model2.evaluate([encoder_input_data_val, decoder_input_data_val], decoder_target_data_val)
print(".001 LR")
model3.evaluate([encoder_input_data_val, decoder_input_data_val], decoder_target_data_val)

encoder_model4, decoder_model4, model4 = encoder_decoder(latent_dim, new_latent_dim, num_encoder_tokens_train, num_decoder_tokens_train)
encoder_model5, decoder_model5, model5 = encoder_decoder(latent_dim, new_latent_dim, num_encoder_tokens_train, num_decoder_tokens_train)
encoder_model6, decoder_model6, model6 = encoder_decoder(latent_dim, new_latent_dim, num_encoder_tokens_train, num_decoder_tokens_train)

model4.compile(optimizer=optimizers.RMSprop(learning_rate=.001), loss='categorical_crossentropy')
model4.fit([encoder_input_data_train, decoder_input_data_train],  
          decoder_target_data_train,                       
          batch_size=64, epochs=50)

model5.compile(optimizer=optimizers.Adam(learning_rate=.001), loss='categorical_crossentropy')
model5.fit([encoder_input_data_train, decoder_input_data_train],  
          decoder_target_data_train,                      
          batch_size=64, epochs=50)

model6.compile(optimizer=optimizers.SGD(learning_rate=.001), loss='categorical_crossentropy')
model6.fit([encoder_input_data_train, decoder_input_data_train],  
          decoder_target_data_train,                      
          batch_size=64, epochs=50)

print("RMSprop")
model4.evaluate([encoder_input_data_val, decoder_input_data_val], decoder_target_data_val)
print("Adam")
model5.evaluate([encoder_input_data_val, decoder_input_data_val], decoder_target_data_val)
print("SGD")
model6.evaluate([encoder_input_data_val, decoder_input_data_val], decoder_target_data_val)

encoder_model7, decoder_model7, model7 = encoder_decoder(latent_dim, new_latent_dim, num_encoder_tokens_train, num_decoder_tokens_train)
encoder_model8, decoder_model8, model8 = encoder_decoder(latent_dim, new_latent_dim, num_encoder_tokens_train, num_decoder_tokens_train)
encoder_model9, decoder_model9, model9 = encoder_decoder(latent_dim, new_latent_dim, num_encoder_tokens_train, num_decoder_tokens_train)

model7.compile(optimizer=optimizers.Adam(learning_rate=.001), loss='categorical_crossentropy')
model7.fit([encoder_input_data_train, decoder_input_data_train],  
          decoder_target_data_train,                       
          batch_size=64, epochs=50)

model8.compile(optimizer=optimizers.Adam(learning_rate=.001), loss='categorical_crossentropy')
model8.fit([encoder_input_data_train, decoder_input_data_train],  
          decoder_target_data_train,                       
          batch_size=128, epochs=50)

model9.compile(optimizer=optimizers.Adam(learning_rate=.001), loss='categorical_crossentropy')
model9.fit([encoder_input_data_train, decoder_input_data_train],  
          decoder_target_data_train,                      
          batch_size=256, epochs=50)


print("64")
model7.evaluate([encoder_input_data_val, decoder_input_data_val], decoder_target_data_val)
print("128")
model8.evaluate([encoder_input_data_val, decoder_input_data_val], decoder_target_data_val)
print("256")
model9.evaluate([encoder_input_data_val, decoder_input_data_val], decoder_target_data_val)


encoder_model_tuned, decoder_model_tuned, model_tuned = encoder_decoder(latent_dim, new_latent_dim, num_encoder_tokens_train, num_decoder_tokens_train)
model_tuned.compile(optimizer=optimizers.Adam(learning_rate=.001), loss='categorical_crossentropy')
model_tuned.fit([encoder_input_data_train, decoder_input_data_train],  
          decoder_target_data_train,                      
          batch_size=64, epochs=50)

model_tuned.evaluate([encoder_input_data_val, decoder_input_data_val], decoder_target_data_val)


from nltk.translate.bleu_score import sentence_bleu
from statistics import mean

reverse_input_char_index_train = dict((i, char) for char, i in input_token_index_train.items())
reverse_target_char_index_train = dict((i, char) for char, i in target_token_index_train.items())

def decode_sequence1(input_seq, encoder_model, decoder_model, reverse_target_char_index, num_decoder_tokens):
    states_value = encoder_model.predict(input_seq)

    target_seq = numpy.zeros((1, 1, num_decoder_tokens))
    target_seq[0, 0, target_token_index['\t']] = 1.

    stop_condition = False
    decoded_sentence = ''
    while not stop_condition:
        output_tokens, h, c = decoder_model.predict([target_seq] + states_value)

        temperature = .25
        pred = output_tokens[0, -1, :].astype('float64')
        pred = pred ** (1/temperature)
        pred = pred / numpy.sum(pred) 
        pred[0] = 0
        sampled_token_index = numpy.argmax(numpy.random.multinomial(1,pred,1))
        sampled_char = reverse_target_char_index[sampled_token_index]
        decoded_sentence += sampled_char

        if (sampled_char == '\n' or
           len(decoded_sentence) > max_decoder_seq_length):
            stop_condition = True

        target_seq = numpy.zeros((1, 1, num_decoder_tokens))
        target_seq[0, 0, sampled_token_index] = 1.

        states_value = [h, c]

    return decoded_sentence

bleu_scores = []
for i in range(100): 
    translation = decode_sequence1(encoder_input_data_test[i:i+1],encoder_model_tuned,decoder_model_tuned, reverse_target_char_index_train, num_decoder_tokens_train)
    truth = target_texts_test[i][1:-1]
    bleu = sentence_bleu([translation], truth)
    print("BLEU: ", bleu)
    bleu_scores.append(bleu)

avg_bleu = mean(bleu_scores)
print("Average BLEU: ", avg_bleu)
    

