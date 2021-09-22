# coding: utf-8
import sys
import time
import numpy as np

from utils import *
from rnnmath import *
from sys import stdout


class RNN(object):
	'''
	This class implements Recurrent Neural Networks.
	
		predict				->	predict an output sequence for a given input sequence
		acc_deltas			->	accumulate update weights for the RNNs weight matrices, standard Back Propagation
		acc_deltas_bptt		->	accumulate update weights for the RNNs weight matrices, using Back Propagation Through Time
		acc_deltas_np		->	accumulate update weights for the RNNs weight matrices, standard Back Propagation -- for number predictions
		acc_deltas_bptt_np	->	accumulate update weights for the RNNs weight matrices, using Back Propagation Through Time -- for number predictions
		compute_loss 		->	compute the (cross entropy) loss between the desired output and predicted output for a given input sequence
		compute_mean_loss	->	compute the average loss over all sequences in a corpus
		generate_sequence	->	use the RNN to generate a new (unseen) sequnce

	'''

	def __init__(self, vocab_size, hidden_dims, out_vocab_size):
		'''
		initialize the RNN with random weight matrices.

		vocab_size		size of vocabulary that is being used
		hidden_dims		number of hidden units
		out_vocab_size	size of the output vocabulary
		'''
		self.vocab_size = vocab_size
		self.hidden_dims = hidden_dims
		self.out_vocab_size = out_vocab_size

		# matrices V (input -> hidden), W (hidden -> output), U (hidden -> hidden)
		self.U = np.random.randn(self.hidden_dims, self.hidden_dims)*np.sqrt(0.1)
		self.V = np.random.randn(self.hidden_dims, self.vocab_size)*np.sqrt(0.1)
		self.W = np.random.randn(self.out_vocab_size, self.hidden_dims)*np.sqrt(0.1)

		# matrices to accumulate weight updates
		self.deltaU = np.zeros((self.hidden_dims, self.hidden_dims))
		self.deltaV = np.zeros((self.hidden_dims, self.vocab_size))
		self.deltaW = np.zeros((self.out_vocab_size, self.hidden_dims))

	def apply_deltas(self, learning_rate):
		'''
		update the RNN's weight matrices with corrections accumulated over some training instances

		learning_rate	scaling factor for update weights
		'''
		# apply updates to U, V, W
		self.U += learning_rate*self.deltaU
		self.W += learning_rate*self.deltaW
		self.V += learning_rate*self.deltaV

		# reset matrices
		self.deltaU.fill(0.0)
		self.deltaV.fill(0.0)
		self.deltaW.fill(0.0)

	def predict(self, x):
		'''
		predict an output sequence y for a given input sequence x

		x	list of words, as indices, e.g.: [0, 4, 2]

		returns	y,s
		y	matrix of probability vectors for each input word
		s	matrix of hidden layers for each input word

		'''

		# matrix s for hidden states, y for output states, given input x.
		# rows correspond to times t, i.e., input words
		# s has one more row, since we need to look back even at time 0 (s(t=0-1) will just be [0. 0. ....] )
		s = np.zeros((len(x) + 1, self.hidden_dims))
		y = np.zeros((len(x), self.out_vocab_size))

		for t in range(len(x)):
			##########################
			x_t_onehot = make_onehot(x[t], self.vocab_size)
			s[t] = sigmoid(np.dot(self.U, s[t-1]) + np.dot(self.V, x_t_onehot))
			y[t] = softmax(np.dot(self.W, s[t]))
			##########################
		return y, s

	def acc_deltas(self, x, d, y, s):
		'''
		accumulate updates for V, W, U
		standard back propagation

		this should not update V, W, U directly. instead, use deltaV, deltaW, deltaU to accumulate updates over time

		x	list of words, as indices, e.g.: [0, 4, 2]
		d	list of words, as indices, e.g.: [4, 2, 3]
		y	predicted output layer for x; list of probability vectors, e.g., [[0.3, 0.1, 0.1, 0.5], [0.2, 0.7, 0.05, 0.05] [...]]
			should be part of the return value of predict(x)
		s	predicted hidden layer for x; list of vectors, e.g., [[1.2, -2.3, 5.3, 1.0], [-2.1, -1.1, 0.2, 4.2], [...]]
			should be part of the return value of predict(x)

		no return values
		'''

		for t in reversed(range(len(x))):
			##########################

			delta_out_t = (make_onehot(d[t], self.out_vocab_size)-y[t])
			delta_in_t = np.dot(self.W.T, delta_out_t)*s[t]*(1-s[t])

			self.deltaW += np.outer(delta_out_t, s[t])
			self.deltaV += np.outer(delta_in_t, make_onehot(x[t], self.vocab_size))
			self.deltaU += np.outer(delta_in_t, s[t-1])
			##########################


	def acc_deltas_np(self, x, d, y, s):
		'''
		accumulate updates for V, W, U
		standard back propagation

		this should not update V, W, U directly. instead, use deltaV, deltaW, deltaU to accumulate updates over time
		for number prediction task, we do binary prediction, 0 or 1

		x	list of words, as indices, e.g.: [0, 4, 2]
		d	array with one element, as indices, e.g.: [0] or [1]
		y	predicted output layer for x; list of probability vectors, e.g., [[0.3, 0.1, 0.1, 0.5], [0.2, 0.7, 0.05, 0.05] [...]]
			should be part of the return value of predict(x)
		s	predicted hidden layer for x; list of vectors, e.g., [[1.2, -2.3, 5.3, 1.0], [-2.1, -1.1, 0.2, 4.2], [...]]
			should be part of the return value of predict(x)

		no return values
		'''

		##########################
		t = len(x)-1
		delta_out_t = make_onehot(d[0], self.out_vocab_size)-y[-1]
		delta_in_t = np.dot(self.W.T, delta_out_t)*s[-2]*(1-s[-2])

		self.deltaW += np.outer(delta_out_t, s[-2])
		self.deltaV += np.outer(delta_in_t, make_onehot(x[-1], self.vocab_size))
		self.deltaU += np.outer(delta_in_t, s[-3])
		##########################


	def acc_deltas_bptt(self, x, d, y, s, steps):
		'''
		accumulate updates for V, W, U
		back propagation through time (BPTT)

		this should not update V, W, U directly. instead, use deltaV, deltaW, deltaU to accumulate updates over time

		x		list of words, as indices, e.g.: [0, 4, 2]
		d		list of words, as indices, e.g.: [4, 2, 3]
		y		predicted output layer for x; list of probability vectors, e.g., [[0.3, 0.1, 0.1, 0.5], [0.2, 0.7, 0.05, 0.05] [...]]
				should be part of the return value of predict(x)
		s		predicted hidden layer for x; list of vectors, e.g., [[1.2, -2.3, 5.3, 1.0], [-2.1, -1.1, 0.2, 4.2], [...]]
				should be part of the return value of predict(x)
		steps	number of time steps to go back in BPTT

		no return values
		'''
		for t in reversed(range(len(x))):
			# print("time {0}".format(t))
			##########################
			delta_out_t = (make_onehot(d[t], self.out_vocab_size)-y[t])
			delta_in_t = np.dot(self.W.T, delta_out_t)*s[t]*(1-s[t])

			steps = min([t,steps])

			delta_in_t_tau = np.copy(delta_in_t)
			for i in range(1,steps+1):
				delta_in_t_tau = np.dot(self.U.T, delta_in_t_tau)*s[t-i]*(1-s[t-i])
				self.deltaV += np.outer(delta_in_t_tau, make_onehot(x[t-i], self.vocab_size))
				self.deltaU += np.outer(delta_in_t_tau, s[t-i-1])

			self.deltaW += np.outer(delta_out_t, s[t])
			self.deltaV += np.outer(delta_in_t, make_onehot(x[t], self.vocab_size))
			self.deltaU += np.outer(delta_in_t, s[t-1])

			##########################


	def acc_deltas_bptt_np(self, x, d, y, s, steps):
		'''
		accumulate updates for V, W, U
		back propagation through time (BPTT)

		this should not update V, W, U directly. instead, use deltaV, deltaW, deltaU to accumulate updates over time
		for number prediction task, we do binary prediction, 0 or 1

		x	list of words, as indices, e.g.: [0, 4, 2]
		d	array with one element, as indices, e.g.: [0] or [1]
		y		predicted output layer for x; list of probability vectors, e.g., [[0.3, 0.1, 0.1, 0.5], [0.2, 0.7, 0.05, 0.05] [...]]
				should be part of the return value of predict(x)
		s		predicted hidden layer for x; list of vectors, e.g., [[1.2, -2.3, 5.3, 1.0], [-2.1, -1.1, 0.2, 4.2], [...]]
				should be part of the return value of predict(x)
		steps	number of time steps to go back in BPTT

		no return values
		'''

		##########################
		t = len(x)-1

		delta_out_t = make_onehot(d[0], self.out_vocab_size)-y[t]
		delta_in_t = np.dot(self.W.T, delta_out_t)*s[t]*(1-s[t])

		steps = min([t,steps])

		delta_in_t_tau = np.copy(delta_in_t)
		for i in range(1,steps+1):
			delta_in_t_tau = np.dot(self.U.T, delta_in_t_tau)*s[t-i]*(1-s[t-i])
			self.deltaV += np.outer(delta_in_t_tau, make_onehot(x[t-i], self.vocab_size))
			self.deltaU += np.outer(delta_in_t_tau, s[t-i-1])

		self.deltaW += np.outer(delta_out_t, s[t])
		self.deltaV += np.outer(delta_in_t, make_onehot(x[t], self.vocab_size))
		self.deltaU += np.outer(delta_in_t, s[t-1])
		##########################


	def compute_loss(self, x, d):
		'''
		compute the loss between predictions y for x, and desired output d.

		first predicts the output for x using the RNN, then computes the loss w.r.t. d

		x		list of words, as indices, e.g.: [0, 4, 2]
		d		list of words, as indices, e.g.: [4, 2, 3]

		return loss		the combined loss for all words
		'''

		loss = 0.

		##########################
		#assert len(x)==len(d)

		y, s = self.predict(x)
		for t in range(len(x)):
			d_t_onehot = make_onehot(d[t], self.out_vocab_size)
			loss -= np.inner(d_t_onehot, np.log(y[t]))
			##########################
		return loss


	def compute_loss_np(self, x, d):
		'''
		compute the loss between predictions y for x, and desired output d.

		first predicts the output for x using the RNN, then computes the loss w.r.t. d

		x		list of words, as indices, e.g.: [0, 4, 2]
		d		a word, as indices, e.g.: [0]

		return loss		we only take the prediction from the last time step
		'''

		loss = 0.

		##########################
		y, s = self.predict(x)
		d_t_onehot = make_onehot(d[0], self.out_vocab_size)
		loss -= np.inner(d_t_onehot, np.log(y[-1]))
		##########################

		return loss


	def compute_acc_np(self, x, d):
		'''
		compute the accuracy prediction, y[t] compared to the desired output d.
		first predicts the output for x using the RNN, then computes the loss w.r.t. d

		x		list of words, as indices, e.g.: [0, 4, 2]
		d		a word class (plural/singular), as index, e.g.: [0] or [1]

		return 1 if argmax(y[t]) == d[0], 0 otherwise
		'''

		y, s = self.predict(x)
		if np.argmax(y[-1]) == d[0]:
			return 1
		return 0


	def compare_num_pred(self, x, d):
		'''
		compute the probability between predictions the desired output d[0] and it's (re)inflected form, d[1].
		first predicts the output for x using the RNN, then compare the probability of d[0] and d[1].

		x		list of words, as indices, e.g.: [0, 4, 2]
		d		the desired verb and its (re)inflected form (singular/plural), as indices, e.g.: [7, 8]

		return 1 if p(d[0]) > p(d[1]), 0 otherwise
		'''

		y, s = self.predict(x)
		if y[-1][d[0]] > y[-1][d[1]]:
			return 1
		return 0


	def compute_acc_lmnp(self, X_dev, D_dev):
		'''
		X_dev			a list of input vectors, e.g., 		[[5, 4, 2], [7, 3, 8]]
		D_dev			a list of pair verb forms (plural/singular), e.g., 	[[4, 9], [6, 5]]
		'''
		acc = sum([self.compare_num_pred(X_dev[i], D_dev[i]) for i in range(len(X_dev))]) / len(X_dev)
		return acc


	def compute_mean_loss(self, X, D):
		'''
		compute the mean loss between predictions for corpus X and desired outputs in corpus D.

		X		corpus of sentences x1, x2, x3, [...], each a list of words as indices.
		D		corpus of desired outputs d1, d2, d3 [...], each a list of words as indices.

		return mean_loss		average loss over all words in D
		'''

		mean_loss = 0.
		total_length = 0
		for i in range(len(X)):
			#
			total_length += len(X[i])
			loss = self.compute_loss(X[i], D[i])
			mean_loss += loss
		mean_loss /= (total_length)

		return mean_loss


	def train(self, X, D, X_dev, D_dev, epochs=10, learning_rate=0.5, anneal=5, back_steps=0, batch_size=100, min_change=0.0001, log=True):
		'''
		train the RNN on some training set X, D while optimizing the loss on a dev set X_dev, D_dev

		training stops after the first of the following is true:
			* number of epochs reached
			* minimum change observed for more than 2 consecutive epochs

		X				a list of input vectors, e.g., 		[[0, 4, 2], [1, 3, 0]]
		D				a list of desired outputs, e.g., 	[[4, 2, 3], [3, 0, 3]]
		X_dev			a list of input vectors, e.g., 		[[0, 4, 2], [1, 3, 0]]
		D_dev			a list of desired outputs, e.g., 	[[4, 2, 3], [3, 0, 3]]
		epochs			maximum number of epochs (iterations) over the training set. default 10
		learning_rate	initial learning rate for training. default 0.5
		anneal			positive integer. if > 0, lowers the learning rate in a harmonically after each epoch.
						higher annealing rate means less change per epoch.
						anneal=0 will not change the learning rate over time.
						default 5
		back_steps		positive integer. number of timesteps for BPTT. if back_steps < 2, standard BP will be used. default 0
		batch_size		number of training instances to use before updating the RNN's weight matrices.
						if set to 1, weights will be updated after each instance. if set to len(X), weights are only updated after each epoch.
						default 100
		min_change		minimum change in loss between 2 epochs. if the change in loss is smaller than min_change, training stops regardless of
						number of epochs left.
						default 0.0001
		log				whether or not to print out log messages. (default log=True)
		'''
		if log:
			stdout.write("\nTraining model for {0} epochs\ntraining set: {1} sentences (batch size {2})".format(epochs, len(X), batch_size))
			stdout.write("\nOptimizing loss on {0} sentences".format(len(X_dev)))
			stdout.write("\nVocab size: {0}\nHidden units: {1}".format(self.vocab_size, self.hidden_dims))
			stdout.write("\nSteps for back propagation: {0}".format(back_steps))
			stdout.write("\nInitial learning rate set to {0}, annealing set to {1}".format(learning_rate, anneal))
			stdout.write("\n\ncalculating initial mean loss on dev set")
			stdout.flush()

		t_start = time.time()
		loss_function = self.compute_loss

		loss_sum = sum([len(d) for d in D_dev])
		initial_loss = sum([loss_function(X_dev[i], D_dev[i]) for i in range(len(X_dev))]) / loss_sum

		if log or not log:
			stdout.write(": {0}\n".format(initial_loss))
			stdout.flush()

		prev_loss = initial_loss
		loss_watch_count = -1
		min_change_count = -1

		a0 = learning_rate

		best_loss = initial_loss
		bestU, bestV, bestW = self.U, self.V, self.W
		best_epoch = 0

		for epoch in range(epochs):
			if anneal > 0:
				learning_rate = a0/((epoch+0.0+anneal)/anneal)
			else:
				learning_rate = a0

			if log:
				stdout.write("\nepoch %d, learning rate %.04f" % (epoch+1, learning_rate))
				stdout.flush()

			t0 = time.time()
			count = 0

			# use random sequence of instances in the training set (tries to avoid local maxima when training on batches)
			permutation = np.random.permutation(range(len(X)))
			if log:
				stdout.write("\tinstance 1")
			for i in range(len(X)):
				c = i+1
				if log:
					stdout.write("\b"*len(str(i)))
					stdout.write("{0}".format(c))
					stdout.flush()
				p = permutation[i]
				x_p = X[p]
				d_p = D[p]

				y_p, s_p = self.predict(x_p)
				if back_steps == 0:
					self.acc_deltas(x_p, d_p, y_p, s_p)
				else:
					self.acc_deltas_bptt(x_p, d_p, y_p, s_p, back_steps)

				if i % batch_size == 0:
					self.deltaU /= batch_size
					self.deltaV /= batch_size
					self.deltaW /= batch_size
					self.apply_deltas(learning_rate)

			if len(X) % batch_size > 0:
				mod = len(X) % batch_size
				self.deltaU /= mod
				self.deltaV /= mod
				self.deltaW /= mod
				self.apply_deltas(learning_rate)

			loss = sum([loss_function(X_dev[i], D_dev[i]) for i in range(len(X_dev))])/loss_sum

			if log:
				stdout.write("\tepoch done in %.02f seconds" % (time.time() - t0))
				stdout.write("\tnew loss: {0}".format(loss))
				stdout.flush()

			if loss < best_loss:
				best_loss = loss
				bestU, bestV, bestW = self.U.copy(), self.V.copy(), self.W.copy()
				best_epoch = epoch

			# make sure we change the RNN enough
			if abs(prev_loss - loss) < min_change:
				min_change_count += 1
			else:
				min_change_count = 0
			if min_change_count > 2:
				print("\n\ntraining finished after {0} epochs due to minimal change in loss".format(epoch+1))
				break

			prev_loss = loss

		t = time.time() - t_start

		if min_change_count <= 2:
			print("\n\ntraining finished after reaching maximum of {0} epochs".format(epochs))
		print("best observed loss was {0}, at epoch {1}".format(best_loss, (best_epoch+1)))

		print("setting U, V, W to matrices from best epoch")
		self.U, self.V, self.W = bestU, bestV, bestW

		return best_loss


	def train_np(self, X, D, X_dev, D_dev, epochs=10, learning_rate=0.5, anneal=5, back_steps=0, batch_size=100, min_change=0.0001, log=True):
		'''
		train the RNN on some training set X, D while optimizing the loss on a dev set X_dev, D_dev

		training stops after the first of the following is true:
			* number of epochs reached
			* minimum change observed for more than 2 consecutive epochs

		X				a list of input vectors, e.g., 		[[5, 4, 2], [7, 3, 8]]
		D				a list of desired outputs, e.g., 	[[0], [1]]
		X_dev			a list of input vectors, e.g., 		[[5, 4, 2], [7, 3, 8]]
		D_dev			a list of desired outputs, e.g., 	[[0], [1]]
		epochs			maximum number of epochs (iterations) over the training set. default 10
		learning_rate	initial learning rate for training. default 0.5
		anneal			positive integer. if > 0, lowers the learning rate in a harmonically after each epoch.
						higher annealing rate means less change per epoch.
						anneal=0 will not change the learning rate over time.
						default 5
		back_steps		positive integer. number of timesteps for BPTT. if back_steps < 2, standard BP will be used. default 0
		batch_size		number of training instances to use before updating the RNN's weight matrices.
						if set to 1, weights will be updated after each instance. if set to len(X), weights are only updated after each epoch.
						default 100
		min_change		minimum change in loss between 2 epochs. if the change in loss is smaller than min_change, training stops regardless of
						number of epochs left.
						default 0.0001
		log				whether or not to print out log messages. (default log=True)
		'''
		if log:
			stdout.write("\nTraining model for {0} epochs\ntraining set: {1} sentences (batch size {2})".format(epochs, len(X), batch_size))
			stdout.write("\nOptimizing loss on {0} sentences".format(len(X_dev)))
			stdout.write("\nVocab size: {0}\nHidden units: {1}".format(self.vocab_size, self.hidden_dims))
			stdout.write("\nSteps for back propagation: {0}".format(back_steps))
			stdout.write("\nInitial learning rate set to {0}, annealing set to {1}".format(learning_rate, anneal))
			stdout.flush()

		t_start = time.time()
		loss_function = self.compute_loss_np

		loss_sum = len(D_dev)
		initial_loss = sum([loss_function(X_dev[i], D_dev[i]) for i in range(len(X_dev))]) / loss_sum
		initial_acc = sum([self.compute_acc_np(X_dev[i], D_dev[i]) for i in range(len(X_dev))]) / len(X_dev)

		if log or not log:
			stdout.write("\n\ncalculating initial mean loss on dev set")
			stdout.write(": {0}\n".format(initial_loss))
			stdout.write("calculating initial acc on dev set")
			stdout.write(": {0}\n".format(initial_acc))
			stdout.flush()

		prev_loss = initial_loss
		loss_watch_count = -1
		min_change_count = -1

		a0 = learning_rate

		best_loss = initial_loss
		bestU, bestV, bestW = self.U, self.V, self.W
		best_epoch = 0

		for epoch in range(epochs):
			if anneal > 0:
				learning_rate = a0/((epoch+0.0+anneal)/anneal)
			else:
				learning_rate = a0

			if log:
				stdout.write("\nepoch %d, learning rate %.04f" % (epoch+1, learning_rate))
				stdout.flush()

			t0 = time.time()
			count = 0

			# use random sequence of instances in the training set (tries to avoid local maxima when training on batches)
			permutation = np.random.permutation(range(len(X)))
			if log:
				stdout.write("\tinstance 1")
			for i in range(len(X)):
				c = i+1
				if log:
					stdout.write("\b"*len(str(i)))
					stdout.write("{0}".format(c))
					stdout.flush()
				p = permutation[i]
				x_p = X[p]
				d_p = D[p]

				y_p, s_p = self.predict(x_p)
				if back_steps == 0:
					self.acc_deltas_np(x_p, d_p, y_p, s_p)
				else:
					self.acc_deltas_bptt_np(x_p, d_p, y_p, s_p, back_steps)

				if i % batch_size == 0:
					self.deltaU /= batch_size
					self.deltaV /= batch_size
					self.deltaW /= batch_size
					self.apply_deltas(learning_rate)

			if len(X) % batch_size > 0:
				mod = len(X) % batch_size
				self.deltaU /= mod
				self.deltaV /= mod
				self.deltaW /= mod
				self.apply_deltas(learning_rate)

			loss = sum([loss_function(X_dev[i], D_dev[i]) for i in range(len(X_dev))]) / loss_sum
			acc = sum([self.compute_acc_np(X_dev[i], D_dev[i]) for i in range(len(X_dev))]) / len(X_dev)
			if epoch == epochs-1:
				print('\n')
				print('Misclassified sentences:')
				for i in range(len(X_dev)):
					x = X_dev[i]
					d = D_dev[i]
					y, s = self.predict(x)
					if np.argmax(y[-1]) != d[0]:
						string = str(i) + ': '
						for j in x:
							string += num_to_word[j]
							string += ' '
						print(string + '| Expected:' + num_to_word[d[0]])
						print(' '.join(sents_dev[i][1:]))



			if log:
				stdout.write("\tepoch done in %.02f seconds" % (time.time() - t0))
				stdout.write("\tnew loss: {0}".format(loss))
				stdout.write("\tnew acc: {0}".format(acc))
				stdout.flush()

			if loss < best_loss:
				best_loss = loss
				best_acc = acc
				bestU, bestV, bestW = self.U.copy(), self.V.copy(), self.W.copy()
				best_epoch = epoch

			# make sure we change the RNN enough
			if abs(prev_loss - loss) < min_change:
				min_change_count += 1
			else:
				min_change_count = 0
			if min_change_count > 2:
				print("\n\ntraining finished after {0} epochs due to minimal change in loss".format(epoch+1))
				break

			prev_loss = loss

		t = time.time() - t_start

		if min_change_count <= 2:
			print("\n\ntraining finished after reaching maximum of {0} epochs".format(epochs))
		print("best observed loss was {0}, acc {1}, at epoch {2}".format(best_loss, best_acc, (best_epoch+1)))

		print("setting U, V, W to matrices from best epoch")
		self.U, self.V, self.W = bestU, bestV, bestW

		return best_loss


if __name__ == "__main__":

	import nltk
	nltk.download('averaged_perceptron_tagger')
	nltk.download('tagsets')

	data_folder = sys.argv[1]
	'''
	EXERCISE 5. Sentences are converted into POS tags and trained as in train-np.
	Needs nltk.pos_tag() installed!
	'''

	train_size = 25000
	dev_size = 1000

	#The POS tags used here
	tagdict = nltk.data.load('help/tagsets/upenn_tagset.pickle')
	set_of_tags = list(tagdict.keys())

	def parse_sents(sentences):
		"""
		Convert sentences to POS tags
		"""
		pos_tags_list = []
		#For each sentence:
		for i in range(len(sentences)):
			#Create a list of tuples of word and pos tag
			tuples = nltk.pos_tag(sentences[i][1:])
			#The number (VBZ or VBP)
			pos_tags = [sentences[i][0]]
			for j in range(len(tuples)):
				#If already a POS tag, keep it
				if tuples[j][0] in set_of_tags:
					pos_tags += [tuples[j][0]]
				#Else, replace with POS tag
				else:
					pos_tags += [tuples[j][1]]
			pos_tags_list += [pos_tags]
		return pos_tags_list

	# load training data
	sents_train = load_np_dataset(data_folder + '/wiki-train.txt')
	sents_train_pos = parse_sents(sents_train[:train_size])
	print(train_size)
	print(len(sents_train_pos))
	# load development data
	sents_dev = load_np_dataset(data_folder + '/wiki-dev.txt')
	sents_dev_pos = parse_sents(sents_dev[:dev_size])

	##########################
	"""
	Get the data set vocabulary by looping over the whole data set
	and appending unknown items
	"""
	vocab = ['VBZ', 'VBP'] # These need to come first
	for i in sents_train_pos+sents_dev_pos:
	    for j in i:
	        if j not in vocab:
	            vocab += [j]
	num_to_word = dict(enumerate(vocab))
	word_to_num = invert_dict(num_to_word)
	vocab_size = len(vocab)
	##########################

	# Finalize data sets
	S_train = docs_to_indices(sents_train_pos, word_to_num, 0, 0)
	X_train, D_train = seqs_to_npXY(S_train)
	S_dev = docs_to_indices(sents_dev_pos, word_to_num, 0, 0)
	X_dev, D_dev = seqs_to_npXY(S_dev)

	#Params
	hidden_dims = 25
	lookback = 20
	lr = 5.0

	rnn = RNN(vocab_size, hidden_dims, 2)
	rnn.train_np(X_train, D_train, X_dev, D_dev, learning_rate=lr, back_steps=lookback, epochs=10, anneal=10, batch_size=50)
