// EchoLookup.kt
package com.example.echoapp

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.material3.Button
import androidx.compose.material3.ElevatedButton
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp

@Composable
fun EchoLookupPanel() {
    val topics = listOf(
        "Ferrum",
        "Talk Nexus X",
        "Dragon Shield Bowling",
        "Nova Frontier",
        "Anything"
    )
    var selectedTopic by remember { mutableStateOf(topics[0]) }
    var queryState by remember { mutableStateOf(TextFieldValue("")) }
    var results by remember { mutableStateOf<List<String>>(emptyList()) }

    Column(modifier = Modifier.padding(16.dp)) {
        Text(
            text = "Look it up",
            style = MaterialTheme.typography.headlineSmall,
            modifier = Modifier.padding(bottom = 8.dp)
        )

        Row(verticalAlignment = Alignment.CenterVertically) {
            TextField(
                value = queryState,
                onValueChange = { queryState = it },
                modifier = Modifier.weight(1f),
                label = { Text("Search query") },
                singleLine = true
            )
            Spacer(modifier = Modifier.width(8.dp))
            ElevatedButton(
                onClick = {
                    // Placeholder search results
                    results = listOf(
                        "Source: Example.com - ${queryState.text} about $selectedTopic line 1",
                        "Source: Sample.org - ${queryState.text} about $selectedTopic line 2",
                        "Source: Demo.io - ${queryState.text} about $selectedTopic line 3"
                    )
                }
            ) {
                Text("Search")
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Topic selector using chips
        Row(
            modifier = Modifier
                .horizontalScroll(rememberScrollState())
                .fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            topics.forEach { topic ->
                FilterChip(
                    selected = selectedTopic == topic,
                    onClick = { selectedTopic = topic },
                    label = { Text(topic) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = MaterialTheme.colorScheme.primaryContainer,
                        selectedLabelColor = MaterialTheme.colorScheme.onPrimaryContainer
                    )
                )
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Results area
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surfaceVariant)
                .padding(8.dp)
                .heightIn(min = 200.dp)
        ) {
            if (results.isEmpty()) {
                Text("No results yet.")
            } else {
                LazyColumn {
                    items(results) { item ->
                        Text(text = item, modifier = Modifier.padding(vertical = 4.dp))
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "Live web search connects when Echo is linked to the computer.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
