module decision_tree_classifier (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    
    // Input: Raw CAN message data
    input  wire [10:0] arb_id_dec,
    input  wire [3:0]  data_length,
    input  wire [7:0]  first_byte,
    input  wire [7:0]  last_byte,
    input  wire [10:0] byte_sum,
    input  wire [31:0] time_delta,
    
    // Output: Classification result
    output reg         done,
    output reg         is_attack,
    output reg  [7:0]  final_node,
    output reg         error,            // Error flag
    output reg  [7:0]  tree_depth        // Độ sâu của cây (debug)
);

    // ========================================================================
    // STATE MACHINE - Cải thiện với thêm states
    // ========================================================================
    localparam IDLE         = 3'd0;
    localparam SCALE        = 3'd1;
    localparam DECODE       = 3'd2;
    localparam COMPARE      = 3'd3;
    localparam NEXT_NODE    = 3'd4;
    localparam CLASSIFY     = 3'd5;
    localparam ERROR_STATE  = 3'd6;
    
    reg [2:0] state, next_state;
    reg [7:0] current_node_addr;
    reg [7:0] depth_counter;
    
    // Max depth protection (tránh infinite loop)
    localparam MAX_DEPTH = 8'd50;
    
    // ========================================================================
    // TREE MEMORY
    // ========================================================================
    reg [63:0] tree_mem [0:172];
    
    initial begin
        $readmemb("tree.mem", tree_mem);
    end
    
    wire [63:0] current_node_data;
    assign current_node_data = tree_mem[current_node_addr];
    
    // ========================================================================
    // PIPELINE CONTROL SIGNALS
    // ========================================================================
    reg        scale_valid;
    wire       scale_done;
    reg        selector_valid;
    wire       selector_done;
    wire       selector_error;
    reg        compare_valid;
    wire       compare_done;
    
    // ========================================================================
    // FEATURE SCALING - Pipelined
    // ========================================================================
    wire [31:0] feature_0_scaled, feature_1_scaled, feature_2_scaled;
    wire [31:0] feature_3_scaled, feature_4_scaled, feature_5_scaled;
    
    feature_scaler scaler (
        .clk(clk),
        .rst_n(rst_n),
        .valid_in(scale_valid),
        .arb_id_dec(arb_id_dec),
        .data_length(data_length),
        .first_byte(first_byte),
        .last_byte(last_byte),
        .byte_sum(byte_sum),
        .time_delta(time_delta),
        .feature_0_scaled(feature_0_scaled),
        .feature_1_scaled(feature_1_scaled),
        .feature_2_scaled(feature_2_scaled),
        .feature_3_scaled(feature_3_scaled),
        .feature_4_scaled(feature_4_scaled),
        .feature_5_scaled(feature_5_scaled),
        .valid_out(scale_done)
    );
    
    // ========================================================================
    // NODE DECODING
    // ========================================================================
    wire [7:0]  node_id;
    wire [2:0]  feature_id;
    wire [26:0] threshold;
    wire [7:0]  right_child, left_child;
    wire [7:0]  node_type;
    wire        is_leaf;
    
    node_decoder decoder (
        .node_data(current_node_data),
        .node_id(node_id),
        .feature_id(feature_id),
        .threshold(threshold),
        .right_child(right_child),
        .left_child(left_child),
        .node_type(node_type),
        .is_leaf(is_leaf)
    );
    
    // ========================================================================
    // FEATURE SELECTION - Pipelined
    // ========================================================================
    wire [31:0] selected_feature;
    
    feature_selector selector (
        .clk(clk),
        .rst_n(rst_n),
        .valid_in(selector_valid),
        .feature_id(feature_id),
        .feature_0_scaled(feature_0_scaled),
        .feature_1_scaled(feature_1_scaled),
        .feature_2_scaled(feature_2_scaled),
        .feature_3_scaled(feature_3_scaled),
        .feature_4_scaled(feature_4_scaled),
        .feature_5_scaled(feature_5_scaled),
        .selected_feature(selected_feature),
        .valid_out(selector_done),
        .error(selector_error)
    );
    
    // ========================================================================
    // THRESHOLD COMPARISON - Pipelined
    // ========================================================================
    wire go_left;
    
    threshold_comparator comparator (
        .clk(clk),
        .rst_n(rst_n),
        .valid_in(compare_valid),
        .feature_value(selected_feature),
        .threshold_raw(threshold),
        .go_left(go_left),
        .valid_out(compare_done)
    );
    
    // ========================================================================
    // NEXT NODE SELECTION
    // ========================================================================
    wire [7:0] next_node;
    assign next_node = go_left ? left_child : right_child;
    
    // ========================================================================
    // STATE MACHINE LOGIC - Improved
    // ========================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            current_node_addr <= 8'd0;
            depth_counter <= 8'd0;
            done <= 1'b0;
            is_attack <= 1'b0;
            final_node <= 8'd0;
            error <= 1'b0;
            tree_depth <= 8'd0;
            scale_valid <= 1'b0;
            selector_valid <= 1'b0;
            compare_valid <= 1'b0;
        end
        else begin
            // Default: clear one-cycle pulses
            scale_valid <= 1'b0;
            selector_valid <= 1'b0;
            compare_valid <= 1'b0;
            
            case (state)
                IDLE: begin
                    done <= 1'b0;
                    error <= 1'b0;
                    if (start) begin
                        current_node_addr <= 8'd0;
                        depth_counter <= 8'd0;
                        scale_valid <= 1'b1;  // Bắt đầu scaling
                        state <= SCALE;
                    end
                end
                
                SCALE: begin
                    if (scale_done) begin
                        state <= DECODE;
                    end
                end
                
                DECODE: begin
                    // Check if leaf node
                    if (is_leaf) begin
                        state <= CLASSIFY;
                        final_node <= current_node_addr;
                        tree_depth <= depth_counter;
                        is_attack <= (node_type == 8'h01);
                    end
                    else begin
                        // Check max depth
                        if (depth_counter >= MAX_DEPTH) begin
                            state <= ERROR_STATE;
                            error <= 1'b1;
                        end
                        else begin
                            selector_valid <= 1'b1;
                            state <= COMPARE;
                        end
                    end
                end
                
                COMPARE: begin
                    if (selector_done) begin
                        if (selector_error) begin
                            state <= ERROR_STATE;
                            error <= 1'b1;
                        end
                        else begin
                            compare_valid <= 1'b1;
                            state <= NEXT_NODE;
                        end
                    end
                end
                
                NEXT_NODE: begin
                    if (compare_done) begin
                        current_node_addr <= next_node;
                        depth_counter <= depth_counter + 1'b1;
                        state <= DECODE;
                    end
                end
                
                CLASSIFY: begin
                    done <= 1'b1;
                    state <= IDLE;
                end
                
                ERROR_STATE: begin
                    done <= 1'b1;
                    error <= 1'b1;
                    state <= IDLE;
                end
                
                default: state <= IDLE;
            endcase
        end
    end

endmodule
