// Example Verilog module to load pure binary MEM file
// This shows how to use the tree.mem file in your FPGA design

module tree_memory (
    input  wire clk,
    input  wire [7:0] addr,
    output reg  [63:0] data
);

    // Memory array: 173 nodes × 64 bits
    reg [63:0] tree_mem [0:172];

    // Load pure binary data from MEM file
    initial begin
        $readmemb("tree.mem", tree_mem);  // Use $readmemb for binary format
    end

    // Read operation
    always @(posedge clk) begin
        data <= tree_mem[addr];
    end

    // Node field extraction
    wire [7:0]  node_id       = data[63:56];
    wire [2:0]  feature_id    = data[55:53];
    wire [26:0] threshold     = data[52:26];
    wire [7:0]  right_child   = data[25:18];
    wire [7:0]  left_child    = data[17:10];
    wire [7:0]  node_type     = data[9:2];
    wire        is_leaf       = (node_type == 8'h01) || 
                                (left_child == 0 && right_child == 0);

endmodule
