# Systemd Service Registration

openSAMPL can be registered as a systemd service to automatically start the server on boot and manage it as a system service.

## Overview

The `opensampl register` command creates and installs a systemd service that will:
- Start the openSAMPL server automatically on boot
- Restart the service if it fails
- Provide standard systemd management commands

## Prerequisites

- Root privileges (sudo access)
- systemd-based Linux distribution
- openSAMPL installed system-wide

## Basic Usage

### Register the Service

To register openSAMPL as a systemd service with default settings:

```bash
sudo opensampl register
```

This will:
- Create a service named `opensampl`
- Run as user `opensampl`
- Use working directory `/opt/opensampl`
- Enable the service to start on boot

### Custom Service Configuration

You can customize the service parameters:

```bash
sudo opensampl register \
  --service-name my-opensampl \
  --user myuser \
  --working-directory /opt/my-opensampl
```

### Uninstall the Service

To remove the systemd service:

```bash
sudo opensampl register --uninstall
```

Or with a custom service name:

```bash
sudo opensampl register --uninstall --service-name my-opensampl
```

## Configuration Management

The systemd service can be configured using configuration files. The system supports two configuration locations:

1. **User Configuration**: `$HOME/.config/opensampl/config` (takes precedence)
2. **System Configuration**: `/etc/opensampl/config` (fallback)

### Setting Configuration Values

Use the `opensampl config set-config` command to set configuration values:

```bash
# Set service name
opensampl config set-config SYSTEMD_SERVICE_NAME my-opensampl

# Set user
opensampl config set-config SYSTEMD_USER opensampl

# Set working directory
opensampl config set-config SYSTEMD_WORKING_DIRECTORY /opt/opensampl

# Set configuration directory
opensampl config set-config SYSTEMD_CONFIG_DIR /etc/opensampl
```

### Viewing Configuration

View all configuration values:

```bash
opensampl config show-config
```

Get a specific configuration value:

```bash
opensampl config get-config SYSTEMD_SERVICE_NAME
```

## Managing the Service

Once registered, you can manage the service using standard systemd commands:

```bash
# Start the service
sudo systemctl start opensampl

# Stop the service
sudo systemctl stop opensampl

# Restart the service
sudo systemctl restart opensampl

# Check service status
sudo systemctl status opensampl

# View service logs
sudo journalctl -u opensampl -f

# Enable/disable auto-start
sudo systemctl enable opensampl
sudo systemctl disable opensampl
```

## Service Configuration

The systemd service is configured with the following defaults:

- **Service Type**: Simple
- **User**: opensampl (or specified user)
- **Working Directory**: /opt/opensampl (or specified directory)
- **ExecStart**: opensampl-server up
- **ExecStop**: opensampl-server down
- **Restart**: Always
- **RestartSec**: 10 seconds
- **WantedBy**: multi-user.target

## Troubleshooting

### Permission Issues

If you encounter permission errors:

1. Ensure you're running with sudo privileges
2. Check that the specified user exists
3. Verify the working directory is accessible

### Service Won't Start

If the service fails to start:

1. Check the service status: `sudo systemctl status opensampl`
2. View the logs: `sudo journalctl -u opensampl -f`
3. Verify the openSAMPL installation: `which opensampl-server`
4. Check the working directory permissions

### Configuration Issues

If configuration isn't being read:

1. Verify the configuration file exists: `ls -la /etc/opensampl/config`
2. Check file permissions: `cat /etc/opensampl/config`
3. Ensure the configuration format is correct (KEY=value)

## Example Workflow

Here's a complete example of setting up openSAMPL as a systemd service:

```bash
# 1. Install openSAMPL (if not already installed)
pip install opensampl

# 2. Configure the service
opensampl config set-config SYSTEMD_SERVICE_NAME opensampl
opensampl config set-config SYSTEMD_USER opensampl
opensampl config set-config SYSTEMD_WORKING_DIRECTORY /opt/opensampl

# 3. Register the service
sudo opensampl register

# 4. Start the service
sudo systemctl start opensampl

# 5. Verify it's running
sudo systemctl status opensampl

# 6. Enable auto-start on boot
sudo systemctl enable opensampl
```

## Security Considerations

- The service runs with the specified user privileges
- Configuration files should have appropriate permissions
- Consider using a dedicated user for the service
- Review the working directory permissions
- Monitor service logs for security-related events 