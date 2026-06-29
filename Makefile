# virtual environment folder
VENV		= .venv

# to use the venv's python once created
PYTHON		= $(VENV)/bin/python3

# to use the venv's pip
PIP			= $(VENV)/bin/pip

# The main script
MAIN		= a_maze_ing.py

# Default config file
CONFIG		= default_config.txt

# "make" with no arguments will run this
all: run

# to reate a virtual environment if it doesn't exist yet
$(VENV):
	python3 -m venv $(VENV)
	@echo "Virtual environment created in $(VENV)/"

# to install pygame into the virtual environment
install: $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install pygame
	@echo "All dependencies installed!"

# runs the maze with the default config file
run: install
	$(PYTHON) $(MAIN) $(CONFIG)

# to remove the virtual environment folder
clean:
	rm -rf $(VENV)
	@echo "Virtual environment removed."

# to remove venv AND any generated output files
fclean: clean
	rm -f maze_output.txt
	@echo "All generated files removed."

# full reset
re: fclean install

#  this line declares targets that are NOT files
.PHONY: all install run clean fclean re