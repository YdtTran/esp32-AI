# Start the Docker STT -> LLM -> Piper -> ESP32 speaker loop.
[CmdletBinding()]
param(
    [string]$DeviceIP = '192.168.1.16',
    [string]$ListenIP = '192.168.1.4',
    [int]$OllamaPort = 11435,
    [string]$UdpSourceIP = '',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$composePath = Join-Path $repoRoot 'infrastructure/voice-compose.yaml'
Write-Host "ESP32: $DeviceIP; PC UDP: ${ListenIP}:5005; speaker HTTP: ${ListenIP}:5006"
if ($DryRun) {
    Write-Host "VOICE_LISTEN_IP=$ListenIP VOICE_DEVICE_IP=$DeviceIP VOICE_OLLAMA_PORT=$OllamaPort"
    Write-Host 'UDP source: explicit -UdpSourceIP, or detected Docker Desktop network gateway.'
    Write-Host "docker compose -f `"$composePath`" up -d --build --wait"
    return
}
$oldListen = $env:VOICE_LISTEN_IP
$oldDevice = $env:VOICE_DEVICE_IP
$oldPort = $env:VOICE_OLLAMA_PORT
$oldSource = $env:VOICE_UDP_SOURCE_IP
try {
    $env:VOICE_LISTEN_IP = $ListenIP
    $env:VOICE_DEVICE_IP = $DeviceIP
    $env:VOICE_OLLAMA_PORT = "$OllamaPort"
    & docker compose -f $composePath config --quiet
    if ($LASTEXITCODE) { throw 'Voice Compose validation failed.' }
    & docker compose -f $composePath build piper voice-loop
    if ($LASTEXITCODE) { throw 'Voice image build failed; existing services left running.' }
    # Transfer only the two project-owned services to the unified stack.
    & docker compose -f (Join-Path $repoRoot 'infrastructure/compose.yaml') stop speaches
    if ($LASTEXITCODE) { throw 'Unable to stop legacy Speaches.' }
    & docker compose -f (Join-Path $repoRoot 'infrastructure/services/ollama/compose.yaml') stop ollama
    if ($LASTEXITCODE) { throw 'Unable to stop legacy Docker Ollama.' }
    & docker compose -f $composePath up -d --wait --wait-timeout 240 speaches ollama piper
    if ($LASTEXITCODE) { throw 'Voice stack startup failed; see docs/specs/speaker-loop.md for rollback.' }
    if (-not $UdpSourceIP) {
        $gateway = & docker network inspect iot-voice_default --format '{{(index .IPAM.Config 0).Gateway}}'
        if ($LASTEXITCODE) { throw 'Unable to detect Docker Desktop UDP forwarding address.' }
        $UdpSourceIP = "$gateway".Trim()
    }
    $parsedSource = $null
    if (-not [System.Net.IPAddress]::TryParse($UdpSourceIP, [ref]$parsedSource) -or
        $parsedSource.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
        throw 'UDP source must be a valid IPv4 address.'
    }
    $env:VOICE_UDP_SOURCE_IP = $UdpSourceIP
    Write-Host "Bridge accepts forwarded UDP source: $UdpSourceIP"
    & docker compose -f $composePath up -d --wait --wait-timeout 120 voice-loop
    if ($LASTEXITCODE) { throw 'Voice loop startup failed; see docs/specs/speaker-loop.md for rollback.' }
    & docker compose -f $composePath ps
} finally {
    $env:VOICE_LISTEN_IP = $oldListen
    $env:VOICE_DEVICE_IP = $oldDevice
    $env:VOICE_OLLAMA_PORT = $oldPort
    $env:VOICE_UDP_SOURCE_IP = $oldSource
}
