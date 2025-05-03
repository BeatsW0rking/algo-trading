import numpy as np
import matplotlib.pyplot as plt

# Define parameters for the two normal distributions
mean = 0
sigma_small = 1   # Small standard deviation (narrow distribution)
sigma_large = 2   # Large standard deviation (wide distribution)

# Generate an array of x values
x = np.linspace(-10, 10, 400)

# Compute the probability density functions (PDF) for both distributions
y_small = (1 / (np.sqrt(2 * np.pi) * sigma_small)) * np.exp(-0.5 * ((x - mean) / sigma_small) ** 2)
y_large = (1 / (np.sqrt(2 * np.pi) * sigma_large)) * np.exp(-0.5 * ((x - mean) / sigma_large) ** 2)

# Create the plot
plt.figure(figsize=(8, 5))
plt.plot(x, y_small, label=f'Small Std Dev (σ = {sigma_small})', linewidth=2)
plt.plot(x, y_large, label=f'Large Std Dev (σ = {sigma_large})', linewidth=2)
plt.title('Normal Distribution Comparison')
plt.xlabel('x')
plt.ylabel('Probability Density')
plt.legend()
plt.grid(True)

# Save the image to a file (optional)
plt.savefig("normal_distribution_comparison.png")

# Display the plot
plt.show()

print('done')
