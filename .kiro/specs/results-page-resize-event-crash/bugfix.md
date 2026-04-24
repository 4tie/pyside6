# Bugfix Requirements Document

## Introduction

The `_reflow` closure inside `ResultsPage._build_pairs_widget` crashes with an
`AttributeError` whenever the pairs-badge container widget is resized. The crash
occurs because the closure attempts to forward the resize event to a parent class
using `super()` on a plain `QWidget` instance, which resolves to `QObject` — a
class that has no `resizeEvent` method.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the pairs-badge container widget receives a resize event THEN the system
    raises `AttributeError: 'super' object has no attribute 'resizeEvent'` because
    `super(type(container), container)` resolves to `QObject`, which does not
    define `resizeEvent`.

1.2 WHEN `type(container)` is the plain `QWidget` class (not a subclass) THEN
    `super(QWidget, container)` yields `QObject`, so any attempt to call
    `.resizeEvent(event)` on that super-proxy fails at runtime.

### Expected Behavior (Correct)

2.1 WHEN the pairs-badge container widget receives a resize event THEN the system
    SHALL forward the event to `QWidget.resizeEvent` directly via
    `QWidget.resizeEvent(container, event)` without raising any exception.

2.2 WHEN `_reflow` is called with a non-None event THEN the system SHALL invoke
    the base `QWidget` resize handling correctly and then reposition all badge
    labels in the flow-wrap layout.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `_reflow` is called with `event=None` (initial layout pass) THEN the
    system SHALL CONTINUE TO position all badge labels in a flow-wrap pattern
    without calling any resize-event forwarding.

3.2 WHEN the pairs list is empty THEN the system SHALL CONTINUE TO return a plain
    dash label without constructing a container or `_reflow` closure.

3.3 WHEN the pairs list is non-empty and the container is resized THEN the system
    SHALL CONTINUE TO reflow badge labels to fit within the container width and
    update the container's minimum height accordingly.
