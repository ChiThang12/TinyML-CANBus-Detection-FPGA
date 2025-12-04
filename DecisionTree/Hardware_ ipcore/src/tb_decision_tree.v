module tb_decision_tree;

    reg clk, rst_n, start;
    reg [10:0] arb_id_dec;
    reg [3:0]  data_length;
    reg [7:0]  first_byte, last_byte;
    reg [10:0] byte_sum;
    reg [31:0] time_delta;
    
    wire done, is_attack, error;
    wire [7:0] final_node, tree_depth;
    
    decision_tree_classifier dut (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .arb_id_dec(arb_id_dec),
        .data_length(data_length),
        .first_byte(first_byte),
        .last_byte(last_byte),
        .byte_sum(byte_sum),
        .time_delta(time_delta),
        .done(done),
        .is_attack(is_attack),
        .final_node(final_node),
        .error(error),
        .tree_depth(tree_depth)
    );
    
    // Clock generation: 10ns period (100MHz)
    initial clk = 0;
    always #5 clk = ~clk;
    
    // Timeout watchdog
    initial begin
        #100000;
        $display("ERROR: Simulation timeout!");
        $finish;
    end
    
    // Test stimulus
    initial begin
        $dumpfile("dt_classifier.vcd");
        $dumpvars(0, tb_decision_tree);
        
        // Initialize
        rst_n = 0;
        start = 0;
        arb_id_dec = 0;
        data_length = 0;
        first_byte = 0;
        last_byte = 0;
        byte_sum = 0;
        time_delta = 0;
        
        #20 rst_n = 1;
        #10;
        
        // Test case 1: Normal message
        $display("\n=== Test 1: Normal Message ===");
        @(posedge clk);
   arb_id_dec  = 11'd510;
   data_length = 5'd16;
   first_byte  = 8'd6;
   last_byte   = 8'd84;
   byte_sum    = 11'd474;
   time_delta  = 32'd0; // microseconds
        start = 1;
        @(posedge clk);
        start = 0;
        
        wait(done);
        if (!error)
            $display("Result: Node=%d, Attack=%b, Depth=%d", 
                     final_node, is_attack, tree_depth);
        else
            $display("ERROR in classification!");
        
        // Test case 2: Potential attack
        #100;
        $display("\n=== Test 2: Potential Attack ===");
        @(posedge clk);
        arb_id_dec = 11'd250;
        data_length = 4'd8;
        first_byte = 8'd200;
        last_byte = 8'd50;
        byte_sum = 11'd800;
        time_delta = 32'd10;
        start = 1;
        @(posedge clk);
        start = 0;
        
        wait(done);
        if (!error)
            $display("Result: Node=%d, Attack=%b, Depth=%d", 
                     final_node, is_attack, tree_depth);
        else
            $display("ERROR in classification!");
        
        // Test case 3: Edge case - minimum values
        #100;
        $display("\n=== Test 3: Edge Case - Min Values ===");
        @(posedge clk);
        arb_id_dec = 11'd0;
        data_length = 4'd0;
        first_byte = 8'd0;
        last_byte = 8'd0;
        byte_sum = 11'd0;
        time_delta = 32'd0;
        start = 1;
        @(posedge clk);
        start = 0;
        
        wait(done);
        if (!error)
            $display("Result: Node=%d, Attack=%b, Depth=%d", 
                     final_node, is_attack, tree_depth);
        else
            $display("ERROR in classification!");
        
        #100;
        $display("\n=== All tests completed ===");
        $finish;
    end
    
    // Monitor signals
    always @(posedge clk) begin
        if (done && !error) begin
            $display("  [%0t] Classification complete", $time);
        end
        if (error) begin
            $display("  [%0t] ERROR detected!", $time);
        end
    end

endmodule