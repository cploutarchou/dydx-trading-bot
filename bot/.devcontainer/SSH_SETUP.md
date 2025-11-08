# SSH Configuration for Dev Container

## SSH Agent Forwarding (Recommended - Secure)

Instead of mounting SSH keys into the container, use SSH agent forwarding for better security.

### Setup SSH Agent Forwarding

1. **Start SSH agent on your host** (if not already running):

   ```bash
   eval "$(ssh-agent -s)"
   ssh-add ~/.ssh/id_rsa  # or your specific key
   ```

2. **VS Code automatically forwards SSH agent** when:
   - Your SSH agent is running
   - You have SSH keys loaded
   - VS Code detects the agent

3. **Verify inside container** (after opening in container):

   ```bash
   # Check if SSH agent is available
   echo $SSH_AUTH_SOCK
   
   # Test SSH connection
   ssh -T git@github.com
   ```

### Alternative: Manual Key Setup (Less Secure)

If SSH agent forwarding doesn't work, you can temporarily generate keys inside the container:

```bash
# Inside the dev container
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
cat ~/.ssh/id_rsa.pub
# Copy the public key to your Git provider
```

### Troubleshooting SSH in Container

**SSH agent not forwarded:**

```bash
# Check if agent is running on host
ssh-add -l

# If no agent, start it
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_rsa
```

**Git authentication fails:**

```bash
# Configure git in container
git config --global user.name "Your Name"
git config --global user.email "your_email@example.com"

# Test connection
ssh -T git@github.com
```

**Use HTTPS instead of SSH (fallback):**

```bash
# Clone/push with HTTPS + token
git clone https://github.com/username/repo.git
git remote set-url origin https://github.com/username/repo.git
```

## Why This Approach?

✅ **Secure**: No SSH private keys copied into container  
✅ **Convenient**: Works automatically with VS Code  
✅ **Clean**: No file system mounts or permission issues  
✅ **Portable**: Works across different environments  

The dev container will now start without SSH mount issues and you can use SSH agent forwarding for secure Git operations.
