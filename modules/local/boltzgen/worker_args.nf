def workerArguments(value) {
    if (value == null || (value instanceof Boolean && !value)) {
        return ''
    }
    if (value instanceof Boolean || !(value.toString() ==~ /\d+/)) {
        throw new IllegalArgumentException('num_workers must be a non-negative integer')
    }
    return "--num_workers ${value}"
}
