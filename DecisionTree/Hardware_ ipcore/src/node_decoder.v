module node_decoder (
    input  wire [63:0] node_data,
    output wire [7:0]  node_id,
    output wire [2:0]  feature_id,
    output wire [26:0] threshold,
    output wire [7:0]  right_child,
    output wire [7:0]  left_child,
    output wire [7:0]  node_type,
    output wire        is_leaf
);

    assign node_id     = node_data[63:56];
    assign feature_id  = node_data[55:53];
    assign threshold   = node_data[52:26];
    assign right_child = node_data[25:18];
    assign left_child  = node_data[17:10];
    assign node_type   = node_data[9:2];
    
    assign is_leaf = (node_type == 8'h01) || 
                     ((left_child == 8'h00) && (right_child == 8'h00));

endmodule
