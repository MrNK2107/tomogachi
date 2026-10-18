"""Comprehensive placement question bank and daily challenges."""

QUESTIONS = [
    # ==========================================
    # DATA STRUCTURES & ALGORITHMS (DSA)
    # ==========================================
    {
        "id": "dsa-01",
        "category": "DSA",
        "topic": "Time Complexity & Heaps",
        "question": "What is the time complexity of building a Binary Heap from an unordered array of N elements using the bottom-up approach (heapify)?",
        "options": [
            "O(N)",
            "O(N log N)",
            "O(log N)",
            "O(N^2)"
        ],
        "correct_index": 0,
        "explanation": "Building a heap bottom-up takes O(N) time because the majority of nodes are near the leaves and have very small heights. Sum of h/2^h converges to a constant.",
        "difficulty": "Medium"
    },
    {
        "id": "dsa-02",
        "category": "DSA",
        "topic": "Sorting & Partitioning",
        "question": "What is the worst-case time complexity of standard QuickSort when elements are already sorted and the last element is always chosen as pivot?",
        "options": [
            "O(N log N)",
            "O(N)",
            "O(N^2)",
            "O(log N)"
        ],
        "correct_index": 2,
        "explanation": "If the array is already sorted and the pivot chosen is always the last element, the partition is extremely unbalanced (1 and N-1 elements each step), yielding O(N^2).",
        "difficulty": "Easy"
    },
    {
        "id": "dsa-03",
        "category": "DSA",
        "topic": "Graph Algorithms",
        "question": "Which algorithm is best suited for finding the shortest path in an unweighted directed/undirected graph?",
        "options": [
            "Dijkstra's Algorithm",
            "Breadth-First Search (BFS)",
            "Bellman-Ford Algorithm",
            "Floyd-Warshall Algorithm"
        ],
        "correct_index": 1,
        "explanation": "For unweighted graphs, BFS visits nodes layer by layer and finds the shortest path in O(V + E) time, outperforming Dijkstra's O(E log V).",
        "difficulty": "Easy"
    },
    {
        "id": "dsa-04",
        "category": "DSA",
        "topic": "Trees & Traversals",
        "question": "Which tree traversal of a Binary Search Tree (BST) produces keys in ascending sorted order?",
        "options": [
            "Preorder traversal",
            "Inorder traversal",
            "Postorder traversal",
            "Level-order traversal"
        ],
        "correct_index": 1,
        "explanation": "Inorder traversal visits (Left, Root, Right). Since for any node in a BST, Left < Root < Right, this always produces ascending order.",
        "difficulty": "Easy"
    },
    {
        "id": "dsa-05",
        "category": "DSA",
        "topic": "Dynamic Programming",
        "question": "Which algorithmic paradigm does the 0/1 Knapsack problem typically require to obtain the optimal solution in pseudo-polynomial time?",
        "options": [
            "Greedy Algorithm",
            "Dynamic Programming",
            "Divide and Conquer",
            "Backtracking without memoization"
        ],
        "correct_index": 1,
        "explanation": "Unlike Fractional Knapsack (which can be solved with Greedy), 0/1 Knapsack has overlapping subproblems and optimal substructure requiring Dynamic Programming.",
        "difficulty": "Medium"
    },
    {
        "id": "dsa-06",
        "category": "DSA",
        "topic": "Hashing",
        "question": "What is the average and worst-case time complexity for search operations in a Hash Table with chaining?",
        "options": [
            "Average: O(1), Worst: O(N)",
            "Average: O(log N), Worst: O(N)",
            "Average: O(1), Worst: O(log N)",
            "Average: O(N), Worst: O(N^2)"
        ],
        "correct_index": 0,
        "explanation": "Under simple uniform hashing, average search is O(1). In the worst case where all keys hash to the same bucket (forming a linked list), it degrades to O(N).",
        "difficulty": "Easy"
    },

    # ==========================================
    # OPERATING SYSTEMS (OS)
    # ==========================================
    {
        "id": "os-01",
        "category": "OS",
        "topic": "Deadlocks",
        "question": "Which of the following is NOT one of Coffman's four conditions required for a Deadlock to occur?",
        "options": [
            "Mutual Exclusion",
            "Hold and Wait",
            "Preemption",
            "Circular Wait"
        ],
        "correct_index": 2,
        "explanation": "The condition is NO Preemption (resources cannot be forcibly taken). Preemption actually PREVENTS deadlocks.",
        "difficulty": "Easy"
    },
    {
        "id": "os-02",
        "category": "OS",
        "topic": "Memory Management",
        "question": "What is 'Thrashing' in an Operating System?",
        "options": [
            "CPU executing high-priority user instructions continuously",
            "High frequency of page faults causing the OS to spend more time swapping pages than executing instructions",
            "A hard drive head crash due to mechanical failure",
            "Multiple threads attempting to write to the same memory address simultaneously"
        ],
        "correct_index": 1,
        "explanation": "Thrashing happens when the working set of active processes exceeds available physical RAM, causing the OS to spend almost 100% of its time on page fault handling and I/O paging.",
        "difficulty": "Medium"
    },
    {
        "id": "os-03",
        "category": "OS",
        "topic": "Process vs Thread",
        "question": "Which resource is typically shared among threads belonging to the same process?",
        "options": [
            "Program Counter (PC)",
            "Stack memory",
            "Register set",
            "Heap memory & Global variables"
        ],
        "correct_index": 3,
        "explanation": "Threads share the text (code), data (globals), and heap memory of their parent process. However, each thread gets its own Program Counter, registers, and Stack.",
        "difficulty": "Medium"
    },
    {
        "id": "os-04",
        "category": "OS",
        "topic": "Synchronization",
        "question": "What is the difference between a Binary Semaphore and a Mutex?",
        "options": [
            "A Mutex has an ownership concept (only the locking thread can unlock it), whereas a Semaphore can be signaled by any thread",
            "Semaphores only work on Linux, Mutexes work on Windows",
            "A Mutex can take integer values up to N, whereas a Semaphore can only be 0 or 1",
            "There is no difference; they are exact synonyms"
        ],
        "correct_index": 0,
        "explanation": "A Mutex is a locking mechanism with ownership: only the thread that acquired it can release it. A Semaphore is a signaling mechanism (an integer counter) where one thread can signal another.",
        "difficulty": "Medium"
    },

    # ==========================================
    # DATABASE MANAGEMENT SYSTEMS (DBMS)
    # ==========================================
    {
        "id": "dbms-01",
        "category": "DBMS",
        "topic": "ACID Properties",
        "question": "In ACID properties of a DBMS, which property ensures that once a transaction has committed, its changes will survive system crashes?",
        "options": [
            "Atomicity",
            "Consistency",
            "Isolation",
            "Durability"
        ],
        "correct_index": 3,
        "explanation": "Durability guarantees that once a transaction commits, its modifications are permanently recorded in non-volatile storage (via WAL/Write-Ahead Logging) and will not be lost even if the system crashes.",
        "difficulty": "Easy"
    },
    {
        "id": "dbms-02",
        "category": "DBMS",
        "topic": "Normalization",
        "question": "A relation is in Boyce-Codd Normal Form (BCNF) if and only if for every non-trivial functional dependency X -> Y:",
        "options": [
            "Y is a subset of X",
            "X is a Superkey",
            "Y is a Prime Attribute",
            "X is a Foreign Key"
        ],
        "correct_index": 1,
        "explanation": "BCNF is a stricter version of 3NF. In BCNF, whenever X -> Y is a non-trivial functional dependency, X MUST be a Superkey.",
        "difficulty": "Medium"
    },
    {
        "id": "dbms-03",
        "category": "DBMS",
        "topic": "Indexing",
        "question": "How many Clustered Indexes can a single table in a relational database like PostgreSQL or SQL Server typically have?",
        "options": [
            "Exactly 1",
            "As many as the number of columns",
            "Up to 16",
            "Unlimited"
        ],
        "correct_index": 0,
        "explanation": "A clustered index determines the actual physical order of data rows on the disk. Since rows can only be physically stored in one order, a table can have only ONE clustered index.",
        "difficulty": "Easy"
    },
    {
        "id": "dbms-04",
        "category": "DBMS",
        "topic": "SQL & Joins",
        "question": "Which type of SQL JOIN returns all rows from the left table, and matching rows from the right table (filling with NULL where there is no match)?",
        "options": [
            "INNER JOIN",
            "LEFT OUTER JOIN",
            "FULL OUTER JOIN",
            "CROSS JOIN"
        ],
        "correct_index": 1,
        "explanation": "LEFT OUTER JOIN returns all records from the left table and matched records from the right table. If no match exists on the right, NULL values are returned for the right columns.",
        "difficulty": "Easy"
    },

    # ==========================================
    # COMPUTER NETWORKS (CN)
    # ==========================================
    {
        "id": "cn-01",
        "category": "CN",
        "topic": "Transport Layer",
        "question": "Which of the following flags are exchanged during the TCP 3-Way Handshake connection establishment?",
        "options": [
            "SYN -> SYN-ACK -> ACK",
            "ACK -> SYN -> SYN-ACK",
            "FIN -> ACK -> FIN-ACK",
            "RST -> SYN -> ACK"
        ],
        "correct_index": 0,
        "explanation": "Client sends SYN to server, server responds with SYN + ACK, and client replies with ACK to complete connection setup.",
        "difficulty": "Easy"
    },
    {
        "id": "cn-02",
        "category": "CN",
        "topic": "OSI & Protocols",
        "question": "At which layer of the OSI model does the Router operate primarily?",
        "options": [
            "Data Link Layer (Layer 2)",
            "Network Layer (Layer 3)",
            "Transport Layer (Layer 4)",
            "Session Layer (Layer 5)"
        ],
        "correct_index": 1,
        "explanation": "Routers forward packets across networks using IP addresses, which operate at Layer 3 (Network Layer). Switches typically operate at Layer 2 (MAC addresses).",
        "difficulty": "Easy"
    },
    {
        "id": "cn-03",
        "category": "CN",
        "topic": "DNS & Application Layer",
        "question": "What transport layer protocol does standard DNS query resolution primarily use for fast lookups?",
        "options": [
            "TCP on port 53",
            "UDP on port 53",
            "HTTP on port 80",
            "ICMP on port 0"
        ],
        "correct_index": 1,
        "explanation": "Standard DNS queries use UDP on port 53 for low latency (no connection handshake overhead). TCP is used when response size exceeds 512 bytes or for zone transfers.",
        "difficulty": "Medium"
    },

    # ==========================================
    # SYSTEM DESIGN & OOP
    # ==========================================
    {
        "id": "sys-01",
        "category": "SYSTEM_DESIGN",
        "topic": "CAP Theorem",
        "question": "According to Brewer's CAP Theorem, in the presence of a network partition (P), a distributed system must choose between which two guarantees?",
        "options": [
            "Consistency (C) and Availability (A)",
            "Concurrency (C) and Accuracy (A)",
            "Caching (C) and Authorization (A)",
            "Compression (C) and Asynchrony (A)"
        ],
        "correct_index": 0,
        "explanation": "Network partitions (P) are inevitable in distributed systems. Therefore, when a partition occurs, a system must decide whether to cancel operations (choose C over A) or proceed with stale data (choose A over C).",
        "difficulty": "Medium"
    },
    {
        "id": "sys-02",
        "category": "OOP",
        "topic": "SOLID Principles",
        "question": "In SOLID principles, what does the 'L' stand for?",
        "options": [
            "Linear Execution Principle",
            "Liskov Substitution Principle",
            "Lazy Evaluation Principle",
            "Loose Coupling Principle"
        ],
        "correct_index": 1,
        "explanation": "Liskov Substitution Principle states that objects of a superclass should be replaceable with objects of a subclass without affecting the correctness of the program.",
        "difficulty": "Easy"
    },

    # ==========================================
    # APTITUDE & LOGICAL REASONING
    # ==========================================
    {
        "id": "apt-01",
        "category": "APTITUDE",
        "topic": "Speed, Time & Distance",
        "question": "A train 120m long passes a pole in 6 seconds. What is the speed of the train in km/hr?",
        "options": [
            "60 km/hr",
            "72 km/hr",
            "84 km/hr",
            "90 km/hr"
        ],
        "correct_index": 1,
        "explanation": "Speed = Distance / Time = 120m / 6s = 20 m/s. Converting to km/hr: 20 * (18 / 5) = 4 * 18 = 72 km/hr.",
        "difficulty": "Easy"
    },
    {
        "id": "apt-02",
        "category": "APTITUDE",
        "topic": "Probability",
        "question": "Two unbiased dice are rolled simultaneously. What is the probability of getting a sum of 7?",
        "options": [
            "1/6",
            "1/12",
            "5/36",
            "7/36"
        ],
        "correct_index": 0,
        "explanation": "Total outcomes = 36. Favorable outcomes for sum 7: (1,6), (2,5), (3,4), (4,3), (5,2), (6,1) = 6 outcomes. Probability = 6/36 = 1/6.",
        "difficulty": "Easy"
    }
]

# Curated LeetCode & Placement Coding Challenges
LEETCODE_DAILY_PROBLEMS = [
    {
        "title": "Two Sum (Hashing & Arrays)",
        "difficulty": "Easy",
        "link": "https://leetcode.com/problems/two-sum/",
        "pattern": "Hash Map Lookup",
        "key_takeaway": "Store complement in dict for O(N) single-pass lookup."
    },
    {
        "title": "Longest Substring Without Repeating Characters",
        "difficulty": "Medium",
        "link": "https://leetcode.com/problems/longest-substring-without-repeating-characters/",
        "pattern": "Sliding Window",
        "key_takeaway": "Maintain left pointer and map of last seen character indices."
    },
    {
        "title": "Merge Intervals",
        "difficulty": "Medium",
        "link": "https://leetcode.com/problems/merge-intervals/",
        "pattern": "Sorting & Greedy",
        "key_takeaway": "Sort by start time, compare current start with previous end."
    },
    {
        "title": "Course Schedule (Detect Cycle in Directed Graph)",
        "difficulty": "Medium",
        "link": "https://leetcode.com/problems/course-schedule/",
        "pattern": "Kahn's Algorithm / Topological Sort",
        "key_takeaway": "Use in-degree array + queue for BFS or 3-color DFS to detect cycles."
    },
    {
        "title": "Coin Change (Fewest Coins to Make Amount)",
        "difficulty": "Medium",
        "link": "https://leetcode.com/problems/coin-change/",
        "pattern": "Bottom-up Dynamic Programming",
        "key_takeaway": "dp[a] = min(dp[a], 1 + dp[a - c]). Initialize with float('inf')."
    },
    {
        "title": "Binary Tree Level Order Traversal",
        "difficulty": "Medium",
        "link": "https://leetcode.com/problems/binary-tree-level-order-traversal/",
        "pattern": "BFS Queue Traversal",
        "key_takeaway": "Track queue length at each level to group nodes by depth."
    },
    {
        "title": "Kth Largest Element in an Array",
        "difficulty": "Medium",
        "link": "https://leetcode.com/problems/kth-largest-element-in-an-array/",
        "pattern": "Min-Heap / QuickSelect",
        "key_takeaway": "Maintain min-heap of size K: O(N log K), or QuickSelect average O(N)."
    }
]

TOPIC_CHEATSHEETS = {
    "DSA": (
        "📚 *DSA Placement Cheatsheet*\n"
        "• Array / Sliding Window: O(N) when subarray size or condition is monotonic\n"
        "• Binary Search: Search space must be monotonic; check mid, mid+1\n"
        "• Tree: Inorder gives sorted in BST; LCA using recursion\n"
        "• Graphs: BFS for shortest path (unweighted), Dijkstra for weighted, Topo-sort for DAG\n"
        "• DP: Look for (1) overlapping subproblems and (2) optimal substructure"
    ),
    "OS": (
        "💻 *OS Placement Cheatsheet*\n"
        "• Process vs Thread: Threads share heap/globals; have private stack/registers\n"
        "• Deadlock Coffman Conditions: Mutual Exclusion, Hold & Wait, No Preemption, Circular Wait\n"
        "• Virtual Memory: Paging divides physical RAM into frames and logical memory into pages\n"
        "• Thrashing: Excessive page faults cause CPU utilization to drop to near zero"
    ),
    "DBMS": (
        "🗄️ *DBMS Placement Cheatsheet*\n"
        "• ACID: Atomicity (All or None), Consistency (Valid states), Isolation (Concurrency), Durability (Persisted)\n"
        "• Normalization: 1NF (atomic values), 2NF (no partial dependency), 3NF (no transitive dependency), BCNF (LHS is superkey)\n"
        "• Index: Clustered (only 1 per table, orders physical rows), Non-clustered (multiple allowed, pointer to row)"
    ),
    "CN": (
        "🌐 *Computer Networks Cheatsheet*\n"
        "• TCP vs UDP: TCP is connection-oriented, reliable, has flow/congestion control. UDP is stateless, low latency\n"
        "• TCP 3-Way Handshake: SYN -> SYN-ACK -> ACK\n"
        "• OSI 7 Layers: Physical, Data Link, Network (IP), Transport (TCP/UDP), Session, Presentation, Application\n"
        "• DNS: Resolves domain to IP over UDP port 53"
    ),
    "APTITUDE": (
        "📐 *Aptitude Formulas Cheatsheet*\n"
        "• Speed Conversion: km/hr to m/s -> multiply by 5/18; m/s to km/hr -> multiply by 18/5\n"
        "• Relative Speed: Same direction = (u - v); Opposite direction = (u + v)\n"
        "• Work & Time: If A does job in x days, 1 day work = 1/x\n"
        "• Probability: P(E) = Favorable Outcomes / Total Outcomes"
    )
}
