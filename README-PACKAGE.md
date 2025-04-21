# Python Package Build and Publish.

### The current approach:

Reads and displays the current version
Shows a warning to remind developers to manually update the version
Only publishes on main branch, using whatever version is currently in pyproject.toml
We still verifies the build works on non-main branches

#### Linting 

Linting configuration is found in the tox.ini
What is enforced is controlled under the [flake8] and [pylint] sections.
