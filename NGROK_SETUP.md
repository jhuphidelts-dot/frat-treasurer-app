# ngrok Permanent URL Setup

## Steps for Permanent URL:

1. **Create free ngrok account** at https://ngrok.com/
2. **Get your auth token** from dashboard
3. **Configure ngrok**:
   ```bash
   ngrok config add-authtoken YOUR_AUTH_TOKEN_HERE
   ```
4. **Reserve a permanent domain** (free tier gets 1 permanent domain)
5. **Start tunnel with permanent domain**:
   ```bash
   ngrok http --domain=your-permanent-domain.ngrok-free.app 8080
   ```

## Benefits:
- ✅ Same URL every time
- ✅ Runs locally on your computer
- ✅ Free tier available
- ✅ Easy to stop/start

## Your brothers would use:
`https://your-permanent-domain.ngrok-free.app`