STATS_MODE = False

def linear_search(callback, min_n, max_n=None):
	
	i = 0
	while True:
		if i - 1 == max_n:
			return None
	
		current = callback(i)
		if not current:
			if i == 0:
				return None
			else:
				return i - 1
		i += 1


def binary_search(callback, min_n, max_n):
	''' Searches for an integer, n, such that n is the last value for which 
		callback returns true.
		
		callback(i): function of argument i to evaluate. Returns True or False.
			On the interval [min_n, max_n + 1], callback must always be False after
			a certain index and is always true at or before that index. Moreover,
			it must be that callback(max_n + 1) = False.
		min_n: lowest value of n to consider.
		post_max: highest value of n to consider.
		
		return: highest n such that callback returns true or None if no such n 
			exists.
	'''
	if min_n > max_n:
		raise Exception("Invalid search range: min_n > max_n")
	
	# Just for measuring number of iterations needed.
	iterations = 0
	
	last_good = None
	a = min_n
	b = max_n
	while True:
		iterations += 1
	
		middle = (a + b) // 2 
		if callback(middle):
			last_good = middle
			a = middle + 1
		else:
			b = middle - 1
			
		last_iteration = last_good == b or a > b
		if last_iteration:
			break
	
	if STATS_MODE:
		print(f"Took {iterations} iterations")
	
	return last_good
	

def exponential_binary_search(callback, min_n, second_guess=None):
	''' Searches for a non-negative integer, n, such that n is the last value for which
		callback returns true. This will search by doubling its guess for n
		until it encounters callback(guess) = False. At this point, it will
		use regular binary serach to deduce n.
		
		callback(i): function of argument i to evaluate. Returns True or False.
			On the interval [min_n, ...], callback must always be False after
			a certain index and is always true at or before that index.
		min_n: lowest value of n to consider.
		second_guess: first guess is always min_n, but set second_guess to
			specify the minimum second value of i to try.
		
		return: highest n such that callback returns true or None if no such n 
			exists. 
	'''
	
	if min_n < 0:
		raise Exception("Minimum n to try is negative.")
	if second_guess is not None and second_guess <= min_n:
		raise Exception("second_guess is not higher than min_n")
	
	if second_guess is None:
		second_guess = min_n + 1
	
	prev_i = None
	i = min_n
	while callback(i):
		prev_i = i
		i = max(i * 2, second_guess)
	
	# If first invocation of callback(i) failed, we know there is no such n
	# where it will return True.
	if i == min_n:
		return None
	
	if i == prev_i + 1:
	
		# No need to bother running binary search.
		return i
	
	# Set up and run regular binary search.
	min_n = prev_i + 1
	max_n = i - 1
	regular_result = binary_search(callback, min_n, max_n)
	if regular_result is None:
	
		# We already know that callback(prev_i) = True.
		return prev_i
	else:
		return regular_result
		

if __name__ == '__main__':
	def make_callback_fn(n):
		return lambda i: i <= n
		
	def expect(expected, actual):
		if actual != expected:
			raise Exception(f"Failed: {expected} != {actual}")
		
	n = 0
	fn = make_callback_fn(n)
	expect(None, binary_search(fn, 2, 32))
	
	n = -10
	fn = make_callback_fn(n)
	expect(None, binary_search(fn, 0, 32))
	
	n = 1
	fn = make_callback_fn(n)
	expect(n, binary_search(fn, 0, 1))
	
	n = 1
	fn = make_callback_fn(n)
	expect(n, binary_search(fn, 1, 32))
		
	fn = make_callback_fn(n)
	expect(n, exponential_binary_search(fn, 1, 32))
		
	n = 0
	fn = make_callback_fn(n)
	expect(n, binary_search(fn, 0, 0))
	expect(n, binary_search(fn, 0, 10))
		
	n = 10
	fn = make_callback_fn(n)
	expect(n, binary_search(fn, 0, 15))
	expect(n, binary_search(fn, 10, 15))
	expect(n, binary_search(fn, 10, 10))
	expect(n, binary_search(fn, 10, 11))
	expect(n, binary_search(fn, 0, 10))
	expect(None, binary_search(fn, 11, 20))
	
	n = 165
	fn = make_callback_fn(n)
	expect(n, exponential_binary_search(fn, 1, 32))
	
	n = 385
	fn = make_callback_fn(n)
	expect(n, exponential_binary_search(fn, 1, 32))
	