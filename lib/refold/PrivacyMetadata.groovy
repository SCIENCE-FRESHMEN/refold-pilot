package refold

class PrivacyMetadata {
    static Object clean(value) {
        if (value instanceof Map) {
            def result = [:]
            value.each { key, item ->
                if (!(key.toString().toLowerCase() ==~ /(?:date|.*_date|timestamp|.*_timestamp|institution|organisation|organization|author|homepage|runname|design_name|germinal_experiment_name|start|complete|account|.*_account|user|username|hostname|email|.*_email|affiliation|.*_affiliation)/)) {
                    result[key] = clean(item)
                }
            }
            return result
        }
        if (value instanceof List) {
            return value.collect { clean(it) }
        }
        if (value instanceof CharSequence) {
            def text = value.toString()
            if (text.startsWith('/') || text ==~ /.*([A-Za-z]:[\\\/]|\/mnt\/[a-z]\/|\/home\/|\/scratch\d*\/|\/fs\d+\/|https?:\/\/|[\w.+-]+@[\w.-]+\.[A-Za-z]+).*/) {
                return '[redacted]'
            }
            return text.replaceAll(/\b(?:19|20)\d{2}[-\/]\d{1,2}[-\/]\d{1,2}\b/, '[redacted]')
                       .replaceAll(/(?i)\b(?:university|institute|college)\b/, '[redacted]')
        }
        return value
    }
}
