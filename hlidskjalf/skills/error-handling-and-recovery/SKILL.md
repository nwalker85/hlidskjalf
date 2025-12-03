---
name: error-handling-and-recovery
description: Manage errors gracefully and ensure task continuity.
version: 1.0.0
author: Norns
tags:
- error-handling
- recovery
- task-continuation
- user-notification
triggers:
- error occurred
- task failure
- exception handling
- error recovery
---

### Error Handling and Recovery Skill

This skill equips the Norns to handle errors gracefully, ensuring that tasks are not interrupted and providing a seamless user experience.

#### Objectives
- Detect when an error occurs and identify its type and context.
- Attempt to resolve the error or provide a workaround if possible.
- Communicate the issue clearly to the user, including potential solutions or next steps.
- Resume the task or offer alternatives to continue the workflow.

#### Instructions
1. **Error Detection**: Monitor for any error messages or failed tool executions.
2. **Identify Context**: Determine the context in which the error occurred (e.g., specific tool, command, or operation).
3. **Resolution Attempt**: If the error is resolvable (e.g., by retrying a command or using a different tool), attempt to fix it.
4. **User Notification**: Inform the user about the error, including what was attempted and any successful resolutions.
5. **Task Continuation**: Automatically attempt to continue with the task or offer the user options to proceed.
6. **Documentation and Learning**: Log errors and resolutions to improve future handling and potentially update skills or tools.

#### Triggers
- Error occurred
- Task failure
- Exception handling
- Error recovery

#### Tags
error-handling, recovery, task-continuation, user-notification
