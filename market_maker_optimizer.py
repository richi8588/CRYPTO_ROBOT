import random
import json
import numpy as np
import logging

from deap import base, creator, tools, algorithms

from market_maker_backtester import run_market_maker_backtest
from utils.logger import log

# --- Genetic Algorithm Configuration ---
POPULATION_SIZE = 20
GENERATIONS = 10
CXPB, MUTPB = 0.7, 0.2 # Crossover and mutation probabilities

# --- Parameter Space (Genes) ---
# We define the range for the spread we want to optimize.
PARAM_SPACE = {
    'spread': (0.0005, 0.005),   # Range: 0.05% to 0.5%
}

# --- DEAP Toolbox Setup ---
creator.create("FitnessMax", base.Fitness, weights=(1.0,))
creator.create("Individual", list, fitness=creator.FitnessMax)

toolbox = base.Toolbox()

toolbox.register("attr_float", random.uniform, *PARAM_SPACE['spread'])
toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.attr_float, n=1)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

# --- Evaluation Function ---
def evaluate(individual):
    """The fitness function. It runs the backtest with the given individual's parameters."""
    spread = individual[0]
    
    # Run the backtest and get the profit
    profit = run_market_maker_backtest(spread)
    
    # DEAP requires a tuple to be returned
    return (profit,)

# Register the genetic operators
toolbox.register("evaluate", evaluate)
toolbox.register("mate", tools.cxBlend, alpha=0.5)
toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=0.2, indpb=0.2)
toolbox.register("select", tools.selTournament, tournsize=3)

# --- Main Execution ---
def main():
    log.setLevel(logging.WARNING) # Reduce verbosity of the backtester
    log.info("--- Starting Market Maker Genetic Algorithm Optimization ---")
    
    pop = toolbox.population(n=POPULATION_SIZE)
    hof = tools.HallOfFame(1) # Hall of Fame to store the best individual
    
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", np.mean)
    stats.register("std", np.std)
    stats.register("min", np.min)
    stats.register("max", np.max)
    
    # Run the algorithm
    algorithms.eaSimple(pop, toolbox, cxpb=CXPB, mutpb=MUTPB, ngen=GENERATIONS, 
                        stats=stats, halloffame=hof, verbose=False)
    
    log.warning("--- Optimization Finished ---")
    
    best_individual = hof[0]
    best_fitness = best_individual.fitness.values[0]
    
    best_params = {
        'spread': best_individual[0]
    }
    
    log.warning(f"Best Individual Found:")
    log.warning(json.dumps(best_params, indent=4))
    log.warning(f"Best Fitness (Profit): {best_fitness:.2f} USD")
    
    # Save the best parameters to a file
    with open('market_maker_best_params.json', 'w') as f:
        json.dump(best_params, f, indent=4)
    log.warning("Best parameters saved to market_maker_best_params.json")

if __name__ == "__main__":
    main()
