# Contributing to OpenSAMPL

We welcome contributions to OpenSAMPL! Here are some guidelines to help you get started:

## Getting Started
1. **Fork the Repository**: Start by forking the OpenSAMPL repository to your own GitHub account.
2. **Pull the Latest Changes**: Make sure your fork is up to date with the main repository.
   ```bash
   git checkout main
   git pull upstream main
   ```
3. **Create a New Branch**: Create a new branch for your feature or bug fix.
   ```bash
   git checkout -b feature/my-feature
   ```
4. **Make Your Changes**: Implement your feature or fix the bug. Ensure your code adheres to the project's coding standards.

   - If you are adding a new feature, consider adding tests to ensure its functionality.
   - If you are fixing a bug, make sure to include a test that reproduces the issue.
5. **Lint, Format, and Type Check Your Changes**: Use the provided tools to lint and format your code.
   ```bash
   ruff check .
   ruff format .
   ty check .
   ```
   This will help maintain code quality and consistency across the project.
6. **Test Your Changes**: Run the tests to ensure your changes do not break anything.
   ```bash
   pytest tests/ 
   ```
7. **Commit Your Changes**: Commit your changes with a clear and concise commit message.
   ```bash
    git commit -m "Add feature X or fix bug Y"
    ```
8. **Push Your Changes**: Push your changes to your forked repository.
0. **Create a Pull Request**: Go to the original OpenSAMPL repository and create a pull request from your branch. Provide a clear description of your changes and why they are needed.
10. **Review Process**: Your pull request will be reviewed by the maintainers. Be open to feedback and make necessary changes.