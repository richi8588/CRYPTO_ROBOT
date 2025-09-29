import random
import json
import numpy as np
import logging

from deap import base, creator, tools, algorithms

from statarb_backtester import run_backtest
from utils.logger import log

# --- Genetic Algorithm Configuration ---
POPULATION_SIZE = 50
GENERATIONS = 20
CXPB, MUTPB = 0.7, 0.2 # Crossover and mutation probabilities

# --- Parameter Space (Genes) ---
# We define the range for each hyperparameter we want to optimize.
PARAM_SPACE = {
    'regression_window': (20, 200), # Range: 20 to 200 hours
    'entry_z_score': (1.5, 3.5),   # Range: 1.5 to 3.5
    'exit_z_score': (0.0, 1.0),    # Range: 0.0 to 1.0
    'stop_loss_z_score': (3.0, 6.0), # Range: 3.0 to 6.0
    'max_holding_period': (24, 120) # Range: 24 to 120 hours
}

# --- DEAP Toolbox Setup ---
# We are trying to maximize the profit, so we use a positive weight.
creator.create("FitnessMax", base.Fitness, weights=(1.0,))
creator.create("Individual", list, fitness=creator.FitnessMax)

toolbox = base.Toolbox()

# Attribute generator: defines how to create a single gene (parameter)
# For integer parameters
toolbox.register("attr_int", random.randint, 0, 0) # Placeholder, will be configured per-param
# For float parameters
toolbox.register("attr_float", random.uniform, 0, 0) # Placeholder

# Structure initializers: defines how to create an individual (a set of parameters)
def create_individual():
    individual = []
    individual.append(random.randint(*PARAM_SPACE['regression_window']))
    individual.append(random.uniform(*PARAM_SPACE['entry_z_score']))
    individual.append(random.uniform(*PARAM_SPACE['exit_z_score']))
    individual.append(random.uniform(*PARAM_SPACE['stop_loss_z_score']))
    individual.append(random.randint(*PARAM_SPACE['max_holding_period']))
    return creator.Individual(individual)

toolbox.register("individual", create_individual)
toolbox.register("population", tools.initRepeat, list, toolbox.individual)

# --- Evaluation Function ---
def evaluate(individual):
    """The fitness function. It runs the backtest with the given individual's parameters."""
    params = {
        'symbol_1': 'DOT',
        'symbol_2': 'DOGE',
        'timeframe': "60",
        'history_limit': 8760, # 1 year of data for consistent evaluation
        'regression_window': int(individual[0]),
        'use_log_spread': True,
        'entry_z_score': individual[1],
        'exit_z_score': individual[2],
        'use_risk_based_sizing': True,
        'max_holding_period': int(individual[4]),
        'stop_loss_z_score': individual[3],
        'slippage_percent': 0.0005,
        'initial_capital': 1000.0,
        'fees_per_trade_leg': 0.001
    }
    
    # Run the backtest and get the profit
    profit = run_backtest(params, plot=False)
    
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
    log.info("--- Starting Genetic Algorithm Optimization ---")
    
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
        'regression_window': int(best_individual[0]),
        'entry_z_score': best_individual[1],
        'exit_z_score': best_individual[2],
        'stop_loss_z_score': best_individual[3],
        'max_holding_period': int(best_individual[4])
    }
    
    log.warning(f"Best Individual Found:")
    log.warning(json.dumps(best_params, indent=4))
    log.warning(f"Best Fitness (Profit): {best_fitness:.2f} USD")
    
    # Save the best parameters to a file
    with open('best_params.json', 'w') as f:
        json.dump(best_params, f, indent=4)
    log.warning("Best parameters saved to best_params.json")

if __name__ == "__main__":
    main()