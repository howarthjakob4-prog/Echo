package com.example.echoapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
class MainActivity : ComponentActivity() {

    // ---------- Data classes ----------
    data class ChatMessage(
        val text: String,
        val timestamp: String,
        var approved: Boolean = false,
        var denied: Boolean = false,
        var isRequest: Boolean = true
    )

    data class LogEntry(val text: String, val timestamp: String)

    // ---------- Main UI ----------
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            EchoApp()
        }
    }

    @Composable
    fun EchoApp() {
        // State variables
        val chatMessages = remember { mutableStateListOf<ChatMessage>() }
        val logEntries = remember { mutableStateListOf<LogEntry>() }
        var inputText by remember { mutableStateOf("") }
        var isConnected by remember { mutableStateOf(false) }
        var isStopped by remember { mutableStateOf(false) }
        var showLookup by remember { mutableStateOf(false) }

        // User greeting log once
        LaunchedEffect(Unit) {
            val time = now()
            logEntries.add(LogEntry("Hello Jakob, Echo ready.", time))
        }

        // Colors
        val backgroundColor = Color(0xFF101010)
        val goldColor = Color(0xFFFFD700)
        val redColor = Color(0xFFB00020)
        val grayColor = Color(0xFF303030)

        MaterialTheme(
            colorScheme = darkColorScheme(
                primary = goldColor,
                secondary = goldColor,
                background = backgroundColor,
                surface = backgroundColor,
                error = redColor,
                onPrimary = Color.Black,
                onSecondary = Color.Black,
                onBackground = Color.White,
                onSurface = Color.White,
                onError = Color.White
            )
        ) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(backgroundColor)
                    .padding(8.dp)
            ) {
                Column(
                    modifier = Modifier.fillMaxSize()
                ) {
                    // Status bar
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 8.dp)
                    ) {
                        Text(
                            text = if (isConnected) "Computer: Connected" else "Computer: Not connected",
                            color = if (isConnected) Color.Green else Color.Red,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.weight(1f)
                        )
                        Button(onClick = { isConnected = !isConnected }) {
                            Text(if (isConnected) "Disconnect" else "Connect")
                        }
                    }

                    // Echo title
                    Text(
                        text = "Echo",
                        color = goldColor,
                        style = MaterialTheme.typography.headlineLarge,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier
                            .align(Alignment.CenterHorizontally)
                            .padding(vertical = 8.dp)
                    )

                    // Quick command buttons
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 8.dp),
                        horizontalArrangement = Arrangement.SpaceEvenly
                    ) {
                        Button(
                            onClick = {
                                val time = now()
                                chatMessages.add(
                                    ChatMessage(
                                        text = "Opening Nova Frontier files...",
                                        timestamp = time,
                                        isRequest = false
                                    )
                                )
                                logEntries.add(LogEntry("Opened Nova Frontier files.", time))
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = grayColor)
                        ) {
                            Text("Open Nova Frontier files")
                        }
                        Button(
                            onClick = {
                                val time = now()
                                val status = if (isConnected) "connected" else "not connected"
                                logEntries.add(LogEntry("Computer status query: $status.", time))
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = grayColor)
                        ) {
                            Text("Check computer status")
                        }
                        Button(
                            onClick = {
                                isStopped = true
                                val time = now()
                                logEntries.add(LogEntry("All operations stopped.", time))
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = redColor)
                        ) {
                            Text("Stop everything")
                        }
                    }

                    // "Look it up" research panel toggle (EchoLookup.kt)
                    Button(
                        onClick = { showLookup = !showLookup },
                        colors = ButtonDefaults.buttonColors(containerColor = grayColor),
                        modifier = Modifier
                            .align(Alignment.CenterHorizontally)
                            .padding(bottom = 8.dp)
                    ) {
                        Text(if (showLookup) "Hide Look it up" else "Look it up")
                    }
                    if (showLookup) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(380.dp)
                                .verticalScroll(rememberScrollState())
                                .background(grayColor)
                                .padding(bottom = 8.dp)
                        ) {
                            EchoLookupPanel()
                        }
                    }

                    // Chat list
                    val chatScroll = rememberScrollState()
                    LazyColumn(
                        modifier = Modifier
                            .weight(1f)
                            .background(grayColor)
                            .padding(8.dp),
                        contentPadding = PaddingValues(4.dp)
                    ) {
                        itemsIndexed(chatMessages) { index, message ->
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(4.dp)
                                    .background(
                                        color = if (index % 2 == 0) Color(0xFF1E1E1E) else Color(0xFF2A2A2A)
                                    )
                                    .padding(8.dp)
                            ) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Text(
                                        text = "[${message.timestamp}]",
                                        color = Color.Gray,
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                    Spacer(modifier = Modifier.width(4.dp))
                                    Text(
                                        text = message.text,
                                        color = if (message.isRequest) Color.Cyan else Color.White,
                                        style = MaterialTheme.typography.bodyMedium
                                    )
                                }
                                if (message.isRequest && !message.approved && !message.denied) {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Row {
                                        Button(
                                            onClick = {
                                                // Replace the item (copy) so Compose sees the change —
                                                // mutating fields in place does not refresh the UI.
                                                chatMessages[index] = message.copy(approved = true, isRequest = false)
                                                val time = now()
                                                chatMessages.add(
                                                    ChatMessage(
                                                        text = "Action approved: ${message.text}",
                                                        timestamp = time,
                                                        isRequest = false
                                                    )
                                                )
                                                logEntries.add(LogEntry("Approved action: ${message.text}", time))
                                            },
                                            colors = ButtonDefaults.buttonColors(containerColor = Color.Green)
                                        ) {
                                            Text("Approve")
                                        }
                                        Spacer(modifier = Modifier.width(8.dp))
                                        Button(
                                            onClick = {
                                                chatMessages[index] = message.copy(denied = true, isRequest = false)
                                                val time = now()
                                                logEntries.add(LogEntry("Denied action: ${message.text}", time))
                                            },
                                            colors = ButtonDefaults.buttonColors(containerColor = Color.Red)
                                        ) {
                                            Text("Deny")
                                        }
                                    }
                                }
                                if (message.denied) {
                                    Text(
                                        text = "Denied",
                                        color = Color.Red,
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                }
                                if (message.approved) {
                                    Text(
                                        text = "Approved",
                                        color = Color.Green,
                                        style = MaterialTheme.typography.bodySmall
                                    )
                                }
                            }
                        }
                    }

                    // Action log
                    Column(
                        modifier = Modifier
                            .height(120.dp)
                            .fillMaxWidth()
                            .background(Color(0xFF191919))
                            .padding(8.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(
                                text = "Action Log",
                                color = goldColor,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.weight(1f)
                            )
                            Button(
                                onClick = { logEntries.clear() },
                                colors = ButtonDefaults.buttonColors(containerColor = grayColor)
                            ) {
                                Text("Clear Log")
                            }
                        }
                        LazyColumn(
                            modifier = Modifier
                                .fillMaxWidth()
                                .weight(1f),
                            contentPadding = PaddingValues(4.dp)
                        ) {
                            itemsIndexed(logEntries) { _, log ->
                                Text(
                                    text = "[${log.timestamp}] ${log.text}",
                                    color = Color.White,
                                    style = MaterialTheme.typography.bodySmall,
                                    modifier = Modifier.padding(2.dp)
                                )
                            }
                        }
                    }

                    // Input field and send button
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        OutlinedTextField(
                            value = inputText,
                            onValueChange = { inputText = it },
                            enabled = !isStopped,
                            modifier = Modifier.weight(1f),
                            placeholder = { Text("Enter command") },
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedContainerColor = Color(0xFF2B2B2B),
                                unfocusedContainerColor = Color(0xFF2B2B2B),
                                disabledContainerColor = Color(0xFF2B2B2B),
                                focusedTextColor = Color.White,
                                unfocusedTextColor = Color.White
                            )
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Button(
                            onClick = {
                                if (inputText.isNotBlank()) {
                                    val time = now()
                                    chatMessages.add(
                                        ChatMessage(
                                            text = inputText,
                                            timestamp = time,
                                            isRequest = true
                                        )
                                    )
                                    logEntries.add(LogEntry("User requested: $inputText", time))
                                    inputText = ""
                                }
                            },
                            enabled = !isStopped,
                            colors = ButtonDefaults.buttonColors(containerColor = goldColor)
                        ) {
                            Text("Send")
                        }
                        Spacer(modifier = Modifier.width(8.dp))
                        Button(
                            onClick = { isStopped = !isStopped },
                            modifier = Modifier.height(56.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = redColor)
                        ) {
                            Text(if (isStopped) "UNSTOP" else "STOP")
                        }
                    }
                }
            }
        }
    }

    // ---------- Helpers ----------
    private fun now() = LocalDateTime.now()
        .format(DateTimeFormatter.ofPattern("HH:mm:ss"))
}
