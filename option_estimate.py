import numpy as np

def binomial_tree_american_option(S0, K, T, r, sigma, N, option_type='call'):
    """
    Function to price an American option using the binomial tree model.

    Parameters:
    S0 (float): Initial stock price
    K (float): Strike price
    T (float): Time to expiration (in years)
    r (float): Risk-free interest rate (annualized)
    sigma (float): Volatility of the underlying stock (annualized)
    N (int): Number of time steps
    option_type (str): 'call' for a call option, 'put' for a put option

    Returns:
    float: The price of the American option
    """

    S0 = float(S0)

    # Calculate time step
    dt = T / N

    # Calculate up and down factors
    u = np.exp(sigma * np.sqrt(dt))
    d = 1 / u

    # Calculate risk-neutral probability
    p = (np.exp(r * dt) - d) / (u - d)

    # Initialize the stock price tree
    stock_tree = np.zeros((N + 1, N + 1))
    for i in range(N + 1):
        for j in range(i + 1):
            stock_tree[j, i] = S0 * (u ** (i - j)) * (d ** j)

    # Initialize the option value tree
    option_tree = np.zeros((N + 1, N + 1))

    # Calculate the option value at expiration
    if option_type == 'call':
        option_tree[:, N] = np.maximum(stock_tree[:, N] - K, 0)
    elif option_type == 'put':
        option_tree[:, N] = np.maximum(K - stock_tree[:, N], 0)

    # Work backward to calculate the option value at each node
    for i in range(N - 1, -1, -1):
        for j in range(i + 1):
            early_exercise = 0
            if option_type == 'call':
                early_exercise = np.maximum(stock_tree[j, i] - K, 0)
            elif option_type == 'put':
                early_exercise = np.maximum(K - stock_tree[j, i], 0)

            continuation_value = np.exp(-r * dt) * (p * option_tree[j, i + 1] + (1 - p) * option_tree[j + 1, i + 1])
            option_tree[j, i] = np.maximum(early_exercise, continuation_value)

    return option_tree[0, 0]

if __name__ == '__main__':

    # Example usage
    S0 = 74.27  # Initial stock price
    K = 74   # Strike price
    T = 216 / 365     # Time to expiration (in years)
    r = 0.0434  # Risk-free interest rate (annualized)
    sigma = 0.5591  # Volatility (annualized)
    N = 216     # Number of time steps

    option_price = binomial_tree_american_option(S0, K, T, r, sigma, N, option_type='put')
    print(f"The price of the American call option is: ${option_price:.2f}")